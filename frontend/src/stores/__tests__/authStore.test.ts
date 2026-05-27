import { describe, it, expect, beforeEach } from 'vitest'
import { useAuthStore } from '../authStore'

describe('authStore', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({ token: null, user: null })
  })

  it('starts with no token', () => {
    expect(useAuthStore.getState().token).toBeNull()
  })

  it('setAuth stores token in localStorage', () => {
    const { setAuth } = useAuthStore.getState()
    setAuth('test-token', { id: '1', display_name: 'Player', onboarding_completed: false })
    expect(localStorage.getItem('token')).toBe('test-token')
    expect(useAuthStore.getState().user?.display_name).toBe('Player')
  })

  it('logout clears token and user', () => {
    const { setAuth, logout } = useAuthStore.getState()
    setAuth('test-token', { id: '1', display_name: 'Player', onboarding_completed: false })
    logout()
    expect(localStorage.getItem('token')).toBeNull()
    expect(useAuthStore.getState().token).toBeNull()
    expect(useAuthStore.getState().user).toBeNull()
  })

  it('reads token from localStorage on init', () => {
    localStorage.setItem('token', 'saved-token')
    useAuthStore.setState({ token: localStorage.getItem('token') })
    expect(useAuthStore.getState().token).toBe('saved-token')
  })
})
