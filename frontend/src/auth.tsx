import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, ApiError } from './api'
import type { ActorResponse, Role } from './types'

export interface AuthSession {
  token: string
  role: Role
  patientId: string | null
  doctorId: string | null
  displayName: string
}

interface AuthContextValue {
  session: AuthSession | null
  ready: boolean
  loginPatient: (mobile: string, name: string) => Promise<void>
  loginDoctor: (doctorId: string) => Promise<void>
  loginStaff: (name: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)
const STORAGE_KEY = 'netracare-session'

function toSession(actor: ActorResponse, token: string): AuthSession {
  return {
    token,
    role: actor.role,
    patientId: actor.patient_id,
    doctorId: actor.doctor_id,
    displayName: actor.display_name,
  }
}

function readStoredSession(): AuthSession | null {
  const raw = window.sessionStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthSession
  } catch {
    window.sessionStorage.removeItem(STORAGE_KEY)
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const stored = readStoredSession()
    if (!stored) {
      setReady(true)
      return
    }
    let ignore = false
    api
      .me(stored.token)
      .then((actor) => {
        if (!ignore) setSession(toSession(actor, stored.token))
      })
      .catch(() => {
        if (!ignore) window.sessionStorage.removeItem(STORAGE_KEY)
      })
      .finally(() => {
        if (!ignore) setReady(true)
      })
    return () => {
      ignore = true
    }
  }, [])

  const establish = useCallback((token: string, actor: ActorResponse) => {
    const nextSession = toSession(actor, token)
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(nextSession))
    setSession(nextSession)
  }, [])

  const loginPatient = useCallback(
    async (mobile: string, name: string) => {
      const auth = await api.loginPatient(mobile, name)
      establish(auth.token, auth)
    },
    [establish],
  )

  const loginDoctor = useCallback(
    async (doctorId: string) => {
      const auth = await api.loginDoctor(doctorId)
      establish(auth.token, auth)
    },
    [establish],
  )

  const loginStaff = useCallback(
    async (name: string) => {
      const auth = await api.loginStaff(name)
      establish(auth.token, auth)
    },
    [establish],
  )

  const logout = useCallback(async () => {
    const current = readStoredSession()
    if (current) {
      try {
        await api.logout(current.token)
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 401) throw error
      }
    }
    window.sessionStorage.removeItem(STORAGE_KEY)
    setSession(null)
  }, [])

  const value = useMemo(
    () => ({ session, ready, loginPatient, loginDoctor, loginStaff, logout }),
    [session, ready, loginPatient, loginDoctor, loginStaff, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
