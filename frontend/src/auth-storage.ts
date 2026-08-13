import type { User } from './auth'

const storageKey = 'user'
export const authenticationRequiredEvent = 'cnvrt-authentication-required'

export function storedUser(): User | null {
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return null
    const value = JSON.parse(raw) as Partial<User> | null
    return value?.access_token ? value as User : null
  } catch {
    return null
  }
}

export function storeUser(user: User | null): void {
  window.localStorage.setItem(storageKey, JSON.stringify(user))
}

export function getStoredAccessToken(): string {
  return storedUser()?.access_token ?? ''
}
