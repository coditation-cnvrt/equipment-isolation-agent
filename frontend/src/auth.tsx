import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { UserContext, useUser } from './auth-context'
import { authenticationRequiredEvent, storedUser, storeUser } from './auth-storage'

const serverBaseUrl = String(import.meta.env.VITE_APP_SERVER_BASE_URL || 'https://api.plant360.ai:8080').replace(/\/$/, '')
const clientId = String(import.meta.env.VITE_APP_OAUTH_CLIENT_ID || '')
const clientSecret = String(import.meta.env.VITE_APP_OAUTH_CLIENT_SECRET || '')
export type UserProfile = {
  id?: string | number
  email?: string
  first_name?: string
  last_name?: string
  super_user?: boolean
}

export type User = {
  access_token: string
  refresh_token?: string
  token_type?: string
  scope?: string
  expires_at?: number
  profile?: UserProfile
}

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(storedUser)
  const login = useCallback((userData: User) => {
    // Persist before rendering authenticated children: their mount effects make
    // immediate API calls whose bearer header is read from localStorage.
    storeUser(userData)
    setUser(userData)
  }, [])
  const logout = useCallback(() => {
    storeUser(null)
    setUser(null)
  }, [])

  useEffect(() => {
    window.addEventListener(authenticationRequiredEvent, logout)
    return () => window.removeEventListener(authenticationRequiredEvent, logout)
  }, [logout])

  return <UserContext.Provider value={{ user, login, logout }}>{children}</UserContext.Provider>
}

type TokenResponse = {
  access_token?: string
  refresh_token?: string
  token_type?: string
  scope?: string
  expires_in?: number
  user?: UserProfile
}

async function signIn(email: string, password: string): Promise<User> {
  if (!clientId || !clientSecret) throw new Error('CNVRT OAuth client is not configured.')
  const body = new URLSearchParams({ grant_type: 'password', username: email, password })
  let response: Response
  try {
    response = await fetch(`${serverBaseUrl}/o/token/`, {
      method: 'POST',
      headers: {
        Authorization: `Basic ${window.btoa(`${clientId}:${clientSecret}`)}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body,
    })
  } catch {
    throw new Error('Authentication service is unavailable.')
  }
  if (response.status === 400 || response.status === 401) throw new Error('Invalid credentials.')
  if (!response.ok) throw new Error('Authentication could not be completed.')
  const token = await response.json() as TokenResponse
  if (!token.access_token) throw new Error('Authentication response did not include an access token.')
  return {
    access_token: token.access_token,
    refresh_token: token.refresh_token,
    token_type: token.token_type,
    scope: token.scope,
    expires_at: token.expires_in,
    profile: token.user,
  }
}

export function SignIn() {
  const { login } = useUser()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      login(await signIn(email, password))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Authentication could not be completed.')
    } finally {
      setPassword('')
      setSubmitting(false)
    }
  }

  return <main className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-950">
    <section className="w-full max-w-md border border-slate-700 bg-white p-8 shadow-2xl">
      <p className="font-mono text-[10px] tracking-[0.16em] text-blue-700">PLANT360</p>
      <h1 className="mt-3 text-2xl font-semibold">Isolation Planning</h1>
      <p className="mt-2 text-sm leading-6 text-slate-600">Sign in with your CNVRT account.</p>
      <form className="mt-7 space-y-5" onSubmit={(event) => void submit(event)}>
        <label className="block text-xs font-medium text-slate-700">Email
          <input autoComplete="username" className="mt-1.5 block h-11 w-full border border-slate-300 px-3 text-sm outline-none focus:border-blue-700" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} />
        </label>
        <label className="block text-xs font-medium text-slate-700">Password
          <input autoComplete="current-password" className="mt-1.5 block h-11 w-full border border-slate-300 px-3 text-sm outline-none focus:border-blue-700" onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
        </label>
        {error && <p className="border-l-2 border-red-500 bg-red-50 px-3 py-2 text-xs text-red-900" role="alert">{error}</p>}
        <button className="h-11 w-full bg-blue-700 font-mono text-xs font-semibold tracking-[0.08em] text-white hover:bg-blue-800 disabled:bg-slate-400" disabled={submitting} type="submit">{submitting ? 'SIGNING IN…' : 'SIGN IN'}</button>
      </form>
      <p className="mt-5 text-center font-mono text-[9px] tracking-wide text-slate-500">ADVISORY PLANNING · NO PLANT ACTION</p>
    </section>
  </main>
}
