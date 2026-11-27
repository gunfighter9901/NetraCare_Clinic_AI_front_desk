"""Iteration 4 LangGraph booking agent: red-flag -> agent <-> tools with confirmation."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from app.llm import EMERGENCY_MESSAGE
from app.rag import CHAT_SAFETY_FAILURE_MESSAGE

STEP_LIMIT_MESSAGE = (
    "Sorry, I can't finish that just now. Please try again, or ask Staff at the front desk."
)

_checkpointer = InMemorySaver()
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()

MUTATION_TOOLS = {"book_appointment", "cancel_appointment", "reschedule_appointment"}


def validate_thread_id(raw: str | None) -> str:
    cleaned = (raw or "").strip()
    if not cleaned or len(cleaned) > 128:
        raise ValueError("thread_id is required (1-128 chars)")
    # Opaque but safe: allow alnum, dash, underscore.
    import re

    if not re.fullmatch(r"[A-Za-z0-9_-]+", cleaned):
        raise ValueError("Invalid thread_id")
    return cleaned


def namespaced_thread(patient_id: str, raw_thread_id: str) -> str:
    return f"{patient_id}:{raw_thread_id}"


def _lock_for(namespaced: str) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(namespaced)
        if lock is None:
            lock = threading.Lock()
            _locks[namespaced] = lock
        return lock


def build_calendar_lines(clock, db) -> list[str]:
    from app.models import Holiday

    now = clock.now()
    today = now.date()
    lines: list[str] = []
    # Preload holidays in window.
    holidays: dict = {}
    try:
        from sqlalchemy import select

        rows = db.scalars(select(Holiday)).all() if db is not None else []
        for h in rows:
            holidays[h.date.isoformat()] = h.name
    except Exception:
        holidays = {}
    for i in range(31):
        d = today + timedelta(days=i)
        weekday = d.strftime("%A")
        if d.weekday() == 6:
            status = "closed (Sunday)"
        elif d.isoformat() in holidays:
            status = f"holiday ({holidays[d.isoformat()]})"
        else:
            status = "open"
        lines.append(f"{d.isoformat()} {weekday}: {status}")
    return lines


def build_system_prompt(*, db, patient, clock) -> str:
    from app.services.appointments import list_upcoming_patient_items

    now = clock.now()
    age = None
    try:
        if getattr(patient, "year_of_birth", None):
            age = now.year - int(patient.year_of_birth)
    except Exception:
        age = None
    try:
        upcoming = list_upcoming_patient_items(db, patient.id, clock) if db is not None else []
    except Exception:
        upcoming = []
    try:
        from app.services.appointments import list_patient_completed_history

        history_rows = list_patient_completed_history(db, patient.id) if db is not None else []
    except Exception:
        history_rows = []
    past_lines = []
    for row in history_rows[:20]:
        try:
            past_lines.append(
                f"{row.date.isoformat()} {row.doctor.name if row.doctor else row.doctor_id} "
                f"{row.speciality} {row.visit_type.value if hasattr(row.visit_type, 'value') else row.visit_type}"
            )
        except Exception:
            continue
    cal = build_calendar_lines(clock, db)
    upcoming_lines = []
    for item in upcoming:
        upcoming_lines.append(
            f"{item['id']} {item['speciality']} with {item['doctor_name']} on {item['date']} {item['start_time']} "
            f"({item['status']}" + (f", {item['approval_status']}" if item.get("approval_status") else "") + ")"
        )
    prompt = "\n".join(
        [
            f"You are NetraCare's booking assistant. Today is {now.date().isoformat()} ({now.strftime('%A')}) at {now.strftime('%H:%M')}.",
            "30-day calendar (date weekday: status):",
            *cal,
            f"Patient: {patient.name}, age {age if age is not None else 'unknown'}.",
            "Upcoming appointments (ID speciality doctor date start status):",
            * (upcoming_lines or ["(none)"]),
            "Past visits (date doctor speciality visit_type):",
            * (past_lines or ["(none)"]),
            "Rules:",
            "- Use find_slots before offering any time; never offer a time not in its results.",
            "- Ask for the visit reason before booking.",
            "- Follow-up only with the doctor of the patient's latest completed visit in that speciality; otherwise new consultation (20 min new, 10 min follow-up). Explain the difference and get agreement before booking as new.",
            "- Under 16 always books Paediatric with Dr. Vikram Menon. For symptom descriptions without a speciality, use documented speciality routing (e.g. high eye pressure -> Glaucoma Dr. Meera Iyer; eye turn in child -> Paediatric/Squint Dr. Vikram Menon).",
            "- Explain refusals in plain words with reason and offer verified free times; if nothing free in 30 days say so clearly.",
            "- Never name a likely condition, never suggest treatment/medicines, never read images/reports, mark costs indicative, nothing outside NetraCare.",
            "- For cancel/reschedule requests naming an appointment, prefer a single reschedule_appointment call over separate cancel+book.",
            "- Booking mutations require confirmation; the tool will pause for it.",
        ]
    )
    return prompt


def select_model_messages(messages: list, limit: int = 20) -> list:
    """Return at most the last `limit` messages without splitting AI tool-call groups."""
    if len(messages) <= limit:
        return list(messages)
    window = list(messages[-limit:])
    # Drop leading ToolMessages that lost their AIMessage.
    while window and isinstance(window[0], ToolMessage):
        window = window[1:]
        if len(window) <= 1:
            break
    # If first message is an AI with tool calls whose tools were cut, keep as is
    # (LangChain tolerates orphaned tool calls better than split groups for this classroom scope).
    # Ensure we don't exceed limit after trimming.
    return window[-limit:]


def to_model_messages(messages: list) -> list:
    """Render checkpoint history for the chat model without native function-call parts.

    Gemini 3.x tool calls require thought signatures that do not survive a
    checkpoint round-trip through LangChain messages. To keep the required
    multi-step loop working, prior tool exchanges are presented as plain-text
    context instead of raw functionCall/tool parts. The current turn still uses
    native tool calling (bound tools), so the model can request the next tool.
    """
    import json as _json

    out: list = []
    idx = 0
    while idx < len(messages):
        msg = messages[idx]
        calls = getattr(msg, "tool_calls", None) if isinstance(msg, AIMessage) else None
        if isinstance(msg, AIMessage) and calls:
            parts = []
            for call in calls:
                name = call.get("name", "") if isinstance(call, dict) else getattr(call, "name", "")
                args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})
                try:
                    parts.append(f"{name}({_json.dumps(args)})")
                except Exception:
                    parts.append(f"{name}(...)")
            text = (getattr(msg, "content", "") or "").strip()
            if text:
                out.append(HumanMessage(content=f"[Your earlier note: {text}]"))
            out.append(
                HumanMessage(
                    content="[You previously requested these tools: "
                    + "; ".join(parts)
                    + ". Their results follow. Use them to decide the next step; do not repeat a completed call.]"
                )
            )
            idx += 1
            results: list[str] = []
            while idx < len(messages) and isinstance(messages[idx], ToolMessage):
                tool_msg = messages[idx]
                results.append(
                    f"{getattr(tool_msg, 'name', 'tool')}: {str(getattr(tool_msg, 'content', ''))[:2000]}"
                )
                idx += 1
            if results:
                out.append(HumanMessage(content="Tool results:\n" + "\n".join(results)))
            continue
        out.append(msg)
        idx += 1
    return out


def _make_graph(*, tools, red_flag_checker, model_factory, clock, step_limit: int = 12):
    from app.services.safety import create_urgent_case
    from app.models import UrgentOrigin

    def red_flag_node(state: MessagesState, config: RunnableConfig) -> dict:
        cfg = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
        # Only the latest human message is the typed message.
        humans = [m for m in state.get("messages", []) if isinstance(m, HumanMessage)]
        if not humans:
            return {}
        text = (humans[-1].content or "").strip() if isinstance(humans[-1].content, str) else ""
        checker = cfg.get("red_flag_checker") or red_flag_checker
        db = cfg.get("db")
        patient = cfg.get("patient")
        clk = cfg.get("clock") or clock
        try:
            result = checker(text) if checker else None
        except Exception as exc:
            from app.llm import LLMCallFailedError, LLMUnavailableError

            # Map any safety failure to the exact chat safety message via marker.
            return {"messages": [AIMessage(content=f"__SAFETY_FAIL__:{CHAT_SAFETY_FAILURE_MESSAGE}")]}
        if result is not None and getattr(result, "red_flag", False):
            urgent_id = None
            urgent_cat = getattr(result, "category", "none")
            try:
                if db is not None and patient is not None:
                    created = create_urgent_case(
                        db,
                        patient_id=patient.id,
                        patient_name=patient.name,
                        patient_mobile=patient.mobile,
                        reason_text=text[:500],
                        category=getattr(result, "category", "none"),
                        model_why=getattr(result, "why", None),
                        now=clk.now(),
                        origin=UrgentOrigin.CHAT,
                    )
                    urgent_id = getattr(created, "id", None)
            except Exception:
                pass
            return {"messages": [AIMessage(content=f"__EMERGENCY__:{EMERGENCY_MESSAGE}", additional_kwargs={"urgent_case_id": urgent_id, "urgent_category": urgent_cat})]}
        return {}

    def agent_node(state: MessagesState, config: RunnableConfig) -> dict:
        cfg = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
        db = cfg.get("db")
        patient = cfg.get("patient")
        clk = cfg.get("clock") or clock
        factory = cfg.get("model_factory") or model_factory
        prompt = build_system_prompt(db=db, patient=patient, clock=clk)
        model = factory(tools) if callable(factory) else factory
        view = select_model_messages(state.get("messages", []), limit=20)
        view = to_model_messages(view)
        # System prompt is transient, not checkpointed.
        from app.config import get_settings

        timeout = get_settings().llm_timeout_seconds
        try:
            ai = model.invoke(
                [SystemMessage(content=prompt)] + view,
                config={"timeout": timeout},
            )
        except Exception as exc:
            # Map model/timeout/step failures to the fixed step message via marker.
            return {"messages": [AIMessage(content=f"__STEP_FAIL__:{STEP_LIMIT_MESSAGE}")]}
        # Guard: at most one mutation per model response is allowed to proceed.
        # The tools node enforces; agent just returns.
        return {"messages": [ai]}

    base_tool_node = ToolNode(tools)

    def tools_node(state: MessagesState, config: RunnableConfig) -> dict:
        msgs = state.get("messages", [])
        last = msgs[-1] if msgs else None
        calls = getattr(last, "tool_calls", None) or []
        mut_calls = [c for c in calls if (c.get("name") if isinstance(c, dict) else getattr(c, "name", "")) in MUTATION_TOOLS]
        if len(mut_calls) > 1:
            # Reject parallel mutations without executing services.
            out = []
            for c in calls:
                cid = c.get("id") if isinstance(c, dict) else getattr(c, "id", "x")
                name = c.get("name") if isinstance(c, dict) else getattr(c, "name", "")
                if name in MUTATION_TOOLS:
                    out.append(ToolMessage(content='{"result": "refused", "reason_code": "PARALLEL_MUTATION", "message": "Confirm one action at a time"}', tool_call_id=cid, name=name))
                else:
                    # Let non-mutations proceed normally via base node; collect later.
                    pass
            # If only mutations were present, return refusals and skip base execution.
            non_mut = [c for c in calls if (c.get("name") if isinstance(c, dict) else getattr(c, "name", "")) not in MUTATION_TOOLS]
            if not non_mut:
                return {"messages": out}
            # Otherwise execute non-mutations via base node and append refusals.
            base_out = base_tool_node.invoke(state, config)
            base_msgs = base_out.get("messages", []) if isinstance(base_out, dict) else []
            return {"messages": out + list(base_msgs)}
        return base_tool_node.invoke(state, config)

    def route_after_red_flag(state: MessagesState) -> str:
        msgs = state.get("messages", []) or []
        if not msgs:
            return "agent"
        last = msgs[-1]
        content = getattr(last, "content", "") or ""
        if isinstance(content, str) and (content.startswith("__EMERGENCY__:") or content.startswith("__SAFETY_FAIL__:")):
            return END
        return "agent"

    def route_after_agent(state: MessagesState) -> str:
        msgs = state.get("messages", []) or []
        if not msgs:
            return END
        last = msgs[-1]
        content = getattr(last, "content", "") or ""
        if isinstance(content, str) and content.startswith("__STEP_FAIL__:"):
            return END
        calls = getattr(last, "tool_calls", None) or []
        if calls:
            return "tools"
        return END

    def route_after_tools(state: MessagesState) -> str:
        msgs = state.get("messages", []) or []
        # Decline-only superseded marker ends without agent follow-up.
        for m in reversed(msgs[-4:]):
            if isinstance(m, ToolMessage):
                try:
                    if "declined_superseded" in str(getattr(m, "content", "")):
                        return END
                except Exception:
                    pass
                break
        return "agent"

    builder = StateGraph(MessagesState)
    builder.add_node("red_flag", red_flag_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tools_node)
    builder.add_edge(START, "red_flag")
    builder.add_conditional_edges("red_flag", route_after_red_flag, {"agent": "agent", END: END})
    builder.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
    builder.add_conditional_edges("tools", route_after_tools, {"agent": "agent", END: END})
    return builder.compile(checkpointer=_checkpointer)


def _default_model_factory(tools):
    from app.llm import _make_model

    model = _make_model(temperature=0)
    try:
        return model.bind_tools(tools)
    except Exception:
        return model


def get_thread_state(namespaced: str) -> dict:
    try:
        snap = _checkpointer.get_tuple({"configurable": {"thread_id": namespaced}})
    except Exception:
        return {"has_pending": False}
    if snap is None:
        return {"has_pending": False}
    # Primary: pending_writes contains __interrupt__ for paused tools.
    try:
        pending_writes = getattr(snap, "pending_writes", None) or []
        for _task_id, channel, value in pending_writes:
            if channel == "__interrupt__":
                vals = value if isinstance(value, list) else [value]
                decoded = [getattr(v, "value", v) for v in vals]
                return {"has_pending": True, "interrupts": decoded}
    except Exception:
        pass
    # Fallback: tasks with interrupts.
    try:
        tasks = getattr(snap, "tasks", None) or ()
        for task in tasks:
            interrupts = getattr(task, "interrupts", None) or ()
            if interrupts:
                vals = [getattr(i, "value", None) for i in interrupts]
                return {"has_pending": True, "interrupts": vals}
    except Exception:
        pass
    # Fallback: values dict.
    try:
        values = getattr(snap, "checkpoint", None) or {}
        # checkpoint is a dict-like with channel_values.
        if isinstance(values, dict):
            cvals = values.get("channel_values", {})
            if isinstance(cvals, dict) and "__interrupt__" in cvals:
                return {"has_pending": True, "interrupts": cvals["__interrupt__"]}
    except Exception:
        pass
    return {"has_pending": False}


def _build_request_graph(*, db, patient, clock, red_flag_checker, model_factory, collection_handle, retrieval_fn, answer_chain, step_limit=12):
    from app.tools import build_tools

    tools = build_tools(
        patient_id=patient.id,
        db=db,
        clock=clock,
        red_flag_checker=red_flag_checker,
        collection_handle=collection_handle,
        retrieval_fn=retrieval_fn,
        answer_chain=answer_chain,
    )
    factory = model_factory or _default_model_factory
    # Wrap factory to bind per-request tools.
    def _factory(_tools=None):
        # _tools arg ignored; use closure tools for binding.
        try:
            return factory(tools)
        except TypeError:
            # Factory expects no args (already bound).
            return factory()
    graph = _make_graph(
        tools=tools,
        red_flag_checker=red_flag_checker,
        model_factory=_factory,
        clock=clock,
        step_limit=step_limit,
    )
    return graph, tools


def _extract_interrupt_payload(invoke_result: dict | None) -> dict | None:
    if not isinstance(invoke_result, dict):
        return None
    items = invoke_result.get("__interrupt__")
    if not items:
        return None
    first = items[0]
    # LangGraph Interrupt object has .value
    val = getattr(first, "value", first)
    if isinstance(val, dict):
        return val
    return None


def _pending_action_from_payload(payload: dict, db) -> dict:
    action = payload.get("action", "book")
    summary = payload.get("summary", "Please confirm?")
    args = payload.get("args", {}) or {}
    out = {
        "action": action,
        "summary": summary,
        "appointment_id": args.get("appointment_id"),
        "doctor_id": args.get("doctor_id"),
        "doctor_name": None,
        "date": args.get("date"),
        "start_time": args.get("start_time"),
        "speciality": args.get("speciality"),
        "visit_type": args.get("visit_type"),
    }
    # Enrich doctor name read-only.
    try:
        if out["doctor_id"]:
            from app.models import Doctor as DoctorModel

            doc = db.get(DoctorModel, out["doctor_id"]) if db is not None else None
            if doc is not None:
                out["doctor_name"] = doc.name
    except Exception:
        pass
    # For cancel, fill doctor/date from original for display.
    try:
        if action in ("cancel", "reschedule") and out.get("appointment_id") and db is not None:
            from app.models import Appointment as ApptModel

            appt = db.get(ApptModel, out["appointment_id"])
            if appt is not None and not out.get("doctor_id"):
                out["doctor_id"] = appt.doctor_id
                out["doctor_name"] = appt.doctor.name if appt.doctor else appt.doctor_id
    except Exception:
        pass
    return out


def _compose_from_turn(*, new_messages: list, interrupt_payload: dict | None, db) -> dict:
    from app.rag import CHAT_UNSUPPORTED_MESSAGE

    # Collect current-turn tool outputs.
    doc_message = None
    doc_sources: list[dict] = []
    doc_answered = False
    doc_response_type = "grounded"
    mutation_outcome = None
    for m in new_messages:
        if isinstance(m, ToolMessage):
            name = getattr(m, "name", "") or ""
            content = getattr(m, "content", "") or ""
            # Tool content is JSON string or dict.
            import json

            try:
                data = json.loads(content) if isinstance(content, str) else content
            except Exception:
                data = {}
            if not isinstance(data, dict):
                data = {}
            if name == "search_clinic_docs":
                if data.get("result") == "ok":
                    doc_response_type = data.get("response_type", "grounded")
                    if doc_response_type == "booking":
                        continue
                    doc_message = data.get("message", "")
                    doc_sources = data.get("sources", []) or []
                    doc_answered = bool(data.get("answered"))
                elif data.get("result") == "error":
                    # Retrieval failure marker.
                    doc_message = "__RAG_FAIL__"
            elif name in MUTATION_TOOLS:
                mutation_outcome = data
    # Emergency / safety / step markers from AI messages.
    for m in new_messages:
        if isinstance(m, AIMessage):
            c = getattr(m, "content", "") or ""
            if isinstance(c, str) and c.startswith("__EMERGENCY__:"):
                kwargs = getattr(m, "additional_kwargs", {}) or {}
                return {"kind": "emergency", "message": c.split("__EMERGENCY__:", 1)[1] if "__EMERGENCY__:" in c else c, "sources": [], "pending_action": None, "urgent_case_id": kwargs.get("urgent_case_id"), "urgent_category": kwargs.get("urgent_category")}
            if isinstance(c, str) and c.startswith("__SAFETY_FAIL__:"):
                return {"kind": "safety_fail", "message": CHAT_SAFETY_FAILURE_MESSAGE, "sources": [], "pending_action": None}
            if isinstance(c, str) and c.startswith("__STEP_FAIL__:"):
                return {"kind": "step_fail", "message": c.split("__STEP_FAIL__:", 1)[1] if "__STEP_FAIL__:" in c else c, "sources": [], "pending_action": None}
    if interrupt_payload is not None:
        pending = _pending_action_from_payload(interrupt_payload, db)
        # Mixed information + card: retain document answer when present.
        if doc_message and doc_message != "__RAG_FAIL__" and doc_response_type == "grounded" and doc_answered:
            message = f"{doc_message}\n\n{pending['summary']}"
            sources = doc_sources
        elif doc_message == "__RAG_FAIL__":
            # Retrieval failed but mutation pending: still show card with unavailable note?
            message = pending["summary"]
            sources = []
        else:
            # No document part: use last AI text if any, else summary.
            ai_texts = [getattr(m, "content", "") for m in new_messages if isinstance(m, AIMessage) and isinstance(getattr(m, "content", ""), str) and not getattr(m, "content", "").startswith("__")]
            base = (ai_texts[-1] if ai_texts else "").strip()
            message = f"{base}\n\n{pending['summary']}".strip() if base else pending["summary"]
            sources = []
        return {"kind": "pending", "message": message, "sources": sources, "pending_action": pending}
    # Final (non-interrupted) composition.
    # RAG failure without pending -> unavailable.
    if doc_message == "__RAG_FAIL__":
        return {"kind": "rag_fail", "message": "", "sources": [], "pending_action": None}
    # Unsupported must be exact with no sources, ignoring agent paraphrase.
    if doc_message is not None and doc_response_type == "grounded" and not doc_answered:
        return {"kind": "answer", "message": CHAT_UNSUPPORTED_MESSAGE, "sources": [], "pending_action": None}
    # Document answer present: use it verbatim (code-owned), not agent paraphrase.
    ai_texts = [getattr(m, "content", "") for m in new_messages if isinstance(m, AIMessage) and isinstance(getattr(m, "content", ""), str) and not getattr(m, "content", "").startswith("__")]
    final_ai = (ai_texts[-1] if ai_texts else "").strip() if ai_texts else ""
    if doc_message and doc_response_type == "grounded" and doc_answered:
        return {"kind": "answer", "message": doc_message, "sources": doc_sources, "pending_action": None}
    # Mutation outcomes without interrupt (should not happen for confirm path without pending, but handle).
    if mutation_outcome:
        res = mutation_outcome.get("result")
        if res in ("booked", "cancelled", "rescheduled", "to_staff", "refused", "declined"):
            return {"kind": "mutation", "message": final_ai or mutation_outcome.get("message", ""), "sources": [], "mutation": mutation_outcome, "pending_action": None}
    return {"kind": "answer", "message": final_ai, "sources": [], "pending_action": None}


def _invoke_with_limit(graph, payload, config: dict, step_limit: int = 12):
    cfg = dict(config or {})
    cfg["recursion_limit"] = step_limit
    try:
        return graph.invoke(payload, config=cfg)
    except Exception as exc:
        # LangGraph recursion overflow.
        name = exc.__class__.__name__
        msg = str(exc).lower()
        if "recursion" in name.lower() or "recursion" in msg or "graphrecursion" in msg:
            return {"__step_limit__": True}
        raise


def run_message_turn(
    *,
    db,
    patient,
    raw_thread_id: str,
    message: str,
    clock,
    red_flag_checker=None,
    model_factory=None,
    collection_handle=None,
    retrieval_fn=None,
    answer_chain=None,
    step_limit: int = 12,
) -> dict:
    raw = validate_thread_id(raw_thread_id)
    ns = namespaced_thread(patient.id, raw)
    lock = _lock_for(ns)
    with lock:
        # If pending exists, decline it first (decline-only, no agent follow-up).
        pending_info = get_thread_state(ns)
        graph, _tools = _build_request_graph(
            db=db, patient=patient, clock=clock,
            red_flag_checker=red_flag_checker, model_factory=model_factory,
            collection_handle=collection_handle, retrieval_fn=retrieval_fn,
            answer_chain=answer_chain, step_limit=step_limit,
        )
        base_config = {"configurable": {
            "thread_id": ns, "patient_id": patient.id,
            "db": db, "patient": patient, "clock": clock,
            "red_flag_checker": red_flag_checker, "model_factory": model_factory,
        }}
        if pending_info.get("has_pending"):
            try:
                _invoke_with_limit(
                    graph, Command(resume={"approved": False, "decline_only": True}),
                    base_config, step_limit,
                )
            except Exception:
                pass
            # Refresh pending check; if still pending (resume failed), treat as no-pending error?
            # Continue to new message regardless (old action is considered declined).
        # Snapshot message count to isolate current turn.
        try:
            before_state = graph.get_state(base_config)
            before_vals = getattr(before_state, "values", None) or {}
            before_msgs = (before_vals.get("messages", []) or []) if isinstance(before_vals, dict) else []
            before_len = len(before_msgs)
        except Exception:
            before_len = 0
        text = (message or "").strip()
        result = _invoke_with_limit(graph, {"messages": [HumanMessage(content=text)]}, base_config, step_limit)
        if isinstance(result, dict) and result.get("__step_limit__"):
            return {"kind": "step_fail", "message": STEP_LIMIT_MESSAGE, "sources": [], "pending_action": None, "raw_result": result, "namespaced": ns}
        payload = _extract_interrupt_payload(result)
        # New messages = state messages after invoke minus before.
        try:
            after_state = graph.get_state(base_config)
            after_vals = getattr(after_state, "values", None) or {}
            after_msgs = (after_vals.get("messages", []) or []) if isinstance(after_vals, dict) else []
            # If interrupted, after_state.values may not include new tool messages yet? Fall back to result messages.
            if not after_msgs and isinstance(result, dict) and "messages" in result:
                after_msgs = result.get("messages", []) or []
            new_messages = list(after_msgs[before_len:]) if len(after_msgs) >= before_len else list(after_msgs)
        except Exception:
            new_messages = (result.get("messages", []) if isinstance(result, dict) else []) or []
        composed = _compose_from_turn(new_messages=new_messages, interrupt_payload=payload, db=db)
        composed["raw_result"] = result
        composed["namespaced"] = ns
        return composed


def resume_confirm_turn(
    *,
    db,
    patient,
    raw_thread_id: str,
    approved: bool,
    clock,
    red_flag_checker=None,
    model_factory=None,
    collection_handle=None,
    retrieval_fn=None,
    answer_chain=None,
    step_limit: int = 12,
) -> dict:
    raw = validate_thread_id(raw_thread_id)
    ns = namespaced_thread(patient.id, raw)
    lock = _lock_for(ns)
    with lock:
        pending_info = get_thread_state(ns)
        if not pending_info.get("has_pending"):
            return {"kind": "no_pending", "message": "No pending action to confirm", "sources": [], "pending_action": None}
        graph, _tools = _build_request_graph(
            db=db, patient=patient, clock=clock,
            red_flag_checker=red_flag_checker, model_factory=model_factory,
            collection_handle=collection_handle, retrieval_fn=retrieval_fn,
            answer_chain=answer_chain, step_limit=step_limit,
        )
        base_config = {"configurable": {
            "thread_id": ns, "patient_id": patient.id,
            "db": db, "patient": patient, "clock": clock,
            "red_flag_checker": red_flag_checker, "model_factory": model_factory,
        }}
        try:
            before_state = graph.get_state(base_config)
            before_vals = getattr(before_state, "values", None) or {}
            before_msgs = (before_vals.get("messages", []) or []) if isinstance(before_vals, dict) else []
            before_len = len(before_msgs)
        except Exception:
            before_len = 0
        resume_val = True if approved else False
        result = _invoke_with_limit(graph, Command(resume=resume_val), base_config, step_limit)
        if isinstance(result, dict) and result.get("__step_limit__"):
            return {"kind": "step_fail", "message": STEP_LIMIT_MESSAGE, "sources": [], "pending_action": None}
        payload = _extract_interrupt_payload(result)
        # If still interrupted (e.g. second mutation in same turn, not allowed), treat as pending again.
        try:
            after_state = graph.get_state(base_config)
            after_vals = getattr(after_state, "values", None) or {}
            after_msgs = (after_vals.get("messages", []) or []) if isinstance(after_vals, dict) else []
            if not after_msgs and isinstance(result, dict) and "messages" in result:
                after_msgs = result.get("messages", []) or []
            new_messages = list(after_msgs[before_len:]) if len(after_msgs) >= before_len else list(after_msgs)
        except Exception:
            new_messages = (result.get("messages", []) if isinstance(result, dict) else []) or []
        if payload is not None:
            composed = _compose_from_turn(new_messages=new_messages, interrupt_payload=payload, db=db)
            composed["raw_result"] = result
            composed["namespaced"] = ns
            return composed
        composed = _compose_from_turn(new_messages=new_messages, interrupt_payload=None, db=db)
        # Attach mutation outcome details for API mapping (booked/refused/to_staff).
        composed["raw_result"] = result
        composed["namespaced"] = ns
        # If declined (No), ensure kind signals agent follow-up.
        if not approved:
            # Agent should have asked what to do instead; keep its message.
            pass
        return composed
