import { useEffect } from 'react'
import { useAuthStore } from '../stores/authStore'

const API = '/api/v1'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { token, setAuth, logout } = useAuthStore()

  useEffect(() => {
    if (!token) return
    fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(u => setAuth(token, u))
      .catch(() => logout())
  }, [])

  return <>{children}</>
}
