import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import type { ChatPendingAction, ChatReply } from '../types'

interface DisplayMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: ChatReply['sources']
  emergency?: boolean
  pendingAction?: ChatPendingAction | null
}

function newThreadId(): string {
  try {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID().replace(/-/g, '').slice(0, 16)
  } catch {
    // fall through
  }
  return `t${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`
}

export default function PatientChat({ onChanged }: { onChanged?: () => void | Promise<void> }) {
  const { session } = useAuth()
  const token = session?.token ?? ''
  const patientId = session?.patientId ?? ''
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<ChatPendingAction | null>(null)
  const generation = useRef(0)
  const threadId = useRef(newThreadId())

  useEffect(() => {
    generation.current += 1
    threadId.current = newThreadId()
    setMessages([])
    setInput('')
    setError(null)
    setPending(null)
  }, [patientId])

  function newChat() {
    generation.current += 1
    threadId.current = newThreadId()
    setMessages([])
    setInput('')
    setError(null)
    setPending(null)
  }

  async function handleReply(reply: ChatReply, base: DisplayMessage[], gen: number) {
    if (generation.current !== gen) return
    const isEmergency = reply.kind === 'emergency'
    const next: DisplayMessage[] = [
      ...base,
      {
        role: 'assistant',
        content: reply.message,
        sources: reply.sources ?? [],
        emergency: isEmergency,
        pendingAction: reply.pending_action ?? null,
      },
    ]
    setMessages(next)
    setPending(reply.pending_action ?? null)
    if (!isEmergency && !reply.pending_action) {
      // Final answer without pending: refresh appointments/slots.
      try {
        await onChanged?.()
      } catch {
        // Non-critical.
      }
    }
  }

  async function send(event?: React.FormEvent) {
    event?.preventDefault()
    const text = input.trim()
    if (!text || sending) return
    if (text.length > 500) {
      setError('Message must be at most 500 characters.')
      return
    }
    const gen = generation.current
    const base: DisplayMessage[] = [...messages, { role: 'user', content: text }]
    setMessages(base)
    setInput('')
    setError(null)
    setSending(true)
    try {
      const reply = await api.chat(token, threadId.current, text, undefined)
      await handleReply(reply, base, gen)
    } catch (caught) {
      if (generation.current !== gen) return
      const message = caught instanceof ApiError ? caught.message : 'Chat failed. Please try again.'
      const emergency = caught instanceof ApiError && /urgent attention/i.test(caught.emergency ?? caught.message)
      setMessages([...base, { role: 'assistant', content: message, sources: [], emergency }])
      if (!emergency) setError(message)
    } finally {
      if (generation.current === gen) setSending(false)
    }
  }

  async function confirm(approved: boolean) {
    if (!pending || sending) return
    const gen = generation.current
    setSending(true)
    setError(null)
    try {
      const reply = await api.chat(token, threadId.current, undefined, approved)
      if (generation.current !== gen) return
      const base: DisplayMessage[] = [
        ...messages,
        { role: 'user', content: approved ? 'Confirm' : 'No' },
      ]
      await handleReply(reply, base, gen)
    } catch (caught) {
      if (generation.current !== gen) return
      const message = caught instanceof ApiError ? caught.message : 'Confirmation failed. Please try again.'
      setError(message)
      if (!approved) setPending(null)
    } finally {
      if (generation.current === gen) setSending(false)
    }
  }

  const showPending = pending && messages.length > 0 && messages[messages.length - 1].pendingAction

  return (
    <section className="card chat-card" aria-label="Patient chat">
      <div className="chat-header">
        <h3>Ask NetraCare</h3>
        <button type="button" onClick={newChat} disabled={sending}>
          New chat
        </button>
      </div>
      <div className="chat-messages">
        {messages.length === 0 && <p className="chat-empty">Ask about timings, fees, procedures, book or change appointments, or describe a problem for speciality guidance.</p>}
        {messages.map((m, idx) => (
          <div key={idx} className={m.role === 'user' ? 'chat-user' : m.emergency ? 'chat-emergency' : 'chat-assistant'}>
            <p>{m.content}</p>
            {m.sources && m.sources.length > 0 && (
              <p className="chat-sources">
                Sources: {m.sources.map((s) => `${s.file} › ${s.section}`).join('; ')}
              </p>
            )}
          </div>
        ))}
        {showPending && pending && (
          <div className="chat-pending" role="group" aria-label="Confirm appointment action">
            <p><strong>{pending.summary}</strong></p>
            <div className="chat-pending-actions">
              <button type="button" onClick={() => void confirm(true)} disabled={sending}>
                Confirm
              </button>
              <button type="button" onClick={() => void confirm(false)} disabled={sending}>
                No
              </button>
            </div>
          </div>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      <form onSubmit={(e) => void send(e)} className="chat-form">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={500}
          placeholder="Ask about the clinic or appointments (max 500 characters)"
          aria-label="Chat message"
        />
        <button type="submit" disabled={sending || !input.trim()}>
          {sending ? 'Sending…' : 'Send'}
        </button>
      </form>
      <p className="caveat">
        Answers come from clinic documents with sources. You can also find free times and book, cancel, or reschedule here after confirming.
      </p>
    </section>
  )
}
