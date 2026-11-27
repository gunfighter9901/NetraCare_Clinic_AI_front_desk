import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api, ApiError } from '../api/client'
import type { ActorResponse, Role } from '../api/client'

export interface Session {
  token: string
  role: Role
  patientId: string | null
  doctorId: string | null
  displayName: string
}

interface SessionValue {
  session: Session | null
  ready: boolean
  login: (token: string, role: Role, patientId: string | null, doctorId: string | null, displayName: string) => void
  logout: () => Promise<void>
}

const SessionContext = createContext<SessionValue | null>(null)

const STORAGE_KEY = 'netracare.session.v1'

function readStored(): Session | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Session
    if (!parsed || typeof parsed.token !== 'string' || !parsed.token) return null
    if (parsed.role !== 'patient' && parsed.role !== 'staff' && parsed.role !== 'doctor') return null
    return parsed
  } catch {
    return null
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(false)
  const sessionRef = useRef<Session | null>(null)
  sessionRef.current = session

  // Validate any restored session against the server before gating on it.
  useEffect(() => {
    const stored = readStored()
    if (!stored) {
      setReady(true)
      return
    }
    let cancelled = false
    api
      .me(stored.token)
      .then((me: ActorResponse) => {
        if (cancelled) return
        const validated: Session = {
          token: stored.token,
          role: me.role,
          patientId: me.patient_id,
          doctorId: me.doctor_id,
          displayName: me.display_name,
        }
        setSession(validated)
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(validated))
        } catch {
          // Storage is best-effort; the in-memory session still works.
        }
      })
      .catch(() => {
        if (cancelled) return
        try {
          localStorage.removeItem(STORAGE_KEY)
        } catch {
          // Ignore storage failures during cleanup.
        }
        setSession(null)
      })
      .finally(() => {
        if (!cancelled) setReady(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(
    (token: string, role: Role, patientId: string | null, doctorId: string | null, displayName: string) => {
      const next: Session = { token, role, patientId, doctorId, displayName }
      setSession(next)
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch {
        // Ignore storage failures; session still works in memory.
      }
    },
    [],
  )

  const logout = useCallback(async () => {
    const current = sessionRef.current
    setSession(null)
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // Ignore storage failures during cleanup.
    }
    if (current) {
      try {
        await api.logout(current.token)
      } catch (error) {
        if (!(error instanceof ApiError)) throw error
        // Server-side logout failure must not keep the client logged in.
      }
    }
  }, [])

  const value = useMemo(() => ({ session, ready, login, logout }), [session, ready, login, logout])
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext)
  if (!value) throw new Error('useSession must be used inside SessionProvider')
  return value
}
