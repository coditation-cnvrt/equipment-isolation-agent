import { createContext, useContext } from 'react'
import type { User } from './auth'

export type UserContextValue = {
  user: User | null
  login: (user: User) => void
  logout: () => void
}

export const UserContext = createContext<UserContextValue | null>(null)

export function useUser(): UserContextValue {
  const context = useContext(UserContext)
  if (!context) throw new Error('useUser must be used inside UserProvider')
  return context
}
