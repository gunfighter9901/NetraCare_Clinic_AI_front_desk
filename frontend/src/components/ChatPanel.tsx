import { useEffect, useRef, useState } from 'react'
import { MessageCircle } from 'lucide-react'
import { api } from '../api/client'
import type { ChatPendingAction, ChatReply, ChatSource } from '../api/client'
import { errorMessage } from '../hooks/useAsync'
import { InlineAlert } from './ui'

interface Message {
  id: string
  role: 'user' | 'assistant'
  text: string
  sources?: ChatSource[]
  emergency?: boolean
  pendingAction?: ChatPendingAction | null
}

function newThreadId(): string {
  return `t-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

export default function ChatPanel({ token, onDataChanged }: { token: string; onDataChanged: () => void }) {
  const [threadId, setThreadId] = useState<string>(() => newThreadId())
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const logRef = useRef<HTMLDivElement>(null)
  let counter = useRef(0)
  const nextId = () => `m-${counter.current++}`

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, pending])

  function reset() {
    setThreadId(newThreadId())
    setMessages([])
    setError(null)
  }

  async function send(message: string) {
    const text = message.trim()
    if (!text || pending) return
    setError(null)
    setPending(true)
    const userMessage: Message = { id: nextId(), role: 'user', text }
    setMessages((previous) => [...previous, userMessage])
    setDraft('')
    try {
      const reply: ChatReply = await api.chat(token, threadId, text)
      appendReply(reply)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setPending(false)
    }
  }

  function appendReply(reply: ChatReply) {
    if (reply.kind === 'emergency') {
      setMessages((previous) => [
        ...previous,
        { id: nextId(), role: 'assistant', text: reply.message, emergency: true },
      ])
      onDataChanged()
      return
    }
    setMessages((previous) => [
      ...previous,
      {
        id: nextId(),
        role: 'assistant',
        text: reply.message,
        sources: reply.sources,
        pendingAction: reply.pending_action ?? null,
      },
    ])
    if (!reply.pending_action) onDataChanged()
  }

  async function confirm(approved: boolean, messageId: string) {
    if (pending) return
    setError(null)
    setPending(true)
    // Remove the confirm card immediately; the outcome message follows.
    setMessages((previous) => previous.map((m) => (m.id === messageId ? { ...m, pendingAction: null } : m)))
    try {
      const reply: ChatReply = await api.chat(token, threadId, undefined, approved)
      if (reply.kind === 'emergency') {
        setMessages((previous) => [
          ...previous,
          { id: nextId(), role: 'assistant', text: reply.message, emergency: true },
        ])
      } else {
        setMessages((previous) => [
          ...previous,
          {
            id: nextId(),
            role: 'assistant',
            text: reply.message || (approved ? 'Done.' : 'Okay, nothing changed.'),
            sources: reply.sources,
            pendingAction: reply.pending_action ?? null,
          },
        ])
      }
      onDataChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="card" aria-label="Clinic assistant chat">
      <div className="entity-row-head" style={{ marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}><MessageCircle size={18} aria-hidden="true" style={{ verticalAlign: '-3px', marginRight: 8 }} />Clinic assistant</h2>
        <button type="button" className="btn btn-secondary btn-sm" onClick={reset} disabled={pending}>
          New chat
        </button>
      </div>
      {messages.length === 0 && (
        <div className="empty-state" style={{ marginBottom: 12 }}>
          Ask about clinic timings, fees, what to bring — or say what bothers your eyes and the
          assistant will route you to the right speciality. Try “What are the clinic timings?”
        </div>
      )}
      <div className="chat-frame">
        <div className="chat-log" ref={logRef} role="log" aria-label="Conversation">
          {messages.map((m) =>
            m.role === 'user' ? (
              <div key={m.id} className="chat-msg chat-user">
                {m.text}
              </div>
            ) : m.emergency ? (
              <div key={m.id} className="chat-msg chat-assistant" style={{ maxWidth: '100%' }}>
                <div className="emergency" role="alert">
                  {m.text}
                </div>
              </div>
            ) : (
              <div key={m.id} className="chat-msg chat-assistant">
                {m.text}
                {m.sources && m.sources.length > 0 && (
                  <span className="chat-sources">
                    {m.sources.map((s, index) => (
                      <span key={`${m.id}-s-${index}`} className="source-chip">
                        {s.file} › {s.section}
                      </span>
                    ))}
                  </span>
                )}
                {m.pendingAction && (
                  <span
                    className="confirm-card"
                    style={{ marginTop: 10, maxWidth: '100%' }}
                  >
                    <strong>{m.pendingAction.summary}</strong>
                    <span style={{ display: 'flex', gap: 8 }}>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        disabled={pending}
                        onClick={() => void confirm(true, m.id)}
                      >
                        Confirm
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        disabled={pending}
                        onClick={() => void confirm(false, m.id)}
                      >
                        No
                      </button>
                    </span>
                  </span>
                )}
              </div>
            ),
          )}
          {pending && (
            <div className="chat-msg chat-assistant" role="status">
              Thinking…
            </div>
          )}
        </div>
        {error && (
          <div style={{ padding: '0 20px' }}>
            <InlineAlert tone="error">{error}</InlineAlert>
          </div>
        )}
        <form
          className="chat-composer"
          onSubmit={(e) => {
            e.preventDefault()
            void send(draft)
          }}
        >
          <label htmlFor="chat-input" className="meta" style={{ position: 'absolute', left: -9999 }}>
            Message the clinic assistant
          </label>
          <input
            id="chat-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type your message (max 500 characters)"
            maxLength={500}
            disabled={pending}
          />
          <button type="submit" className="btn btn-primary" disabled={pending || !draft.trim()} aria-label="Send message">
            Send
          </button>
        </form>
      </div>
    </section>
  )
}
