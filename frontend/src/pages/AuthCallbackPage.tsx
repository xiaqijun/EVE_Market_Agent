import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function AuthCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const setAuth = useAuthStore(s => s.setAuth)

  useEffect(() => {
    const token = searchParams.get('token')
    const userId = searchParams.get('user_id')
    const name = searchParams.get('name')

    if (token && userId) {
      setAuth(token, { id: userId, display_name: name || '', onboarding_completed: false })
      navigate('/', { replace: true })
    } else {
      navigate('/login', { replace: true })
    }
  }, [searchParams, setAuth, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#020810]">
      <div className="text-center text-gray-400">
        <div className="text-2xl mb-3 animate-pulse">◎</div>
        <div className="font-display text-sm tracking-wider">正在登录...</div>
      </div>
    </div>
  )
}
