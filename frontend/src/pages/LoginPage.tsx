import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

const API = '/api/v1'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const setAuth = useAuthStore(s => s.setAuth)
  const navigate = useNavigate()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (res.ok) {
      const data = await res.json()
      setAuth(data.access_token, data.user)
      navigate('/')
    }
  }

  const handleEveLogin = () => {
    window.location.href = `${API}/auth/eve/login`
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#020810]">
      <div className="w-[400px] bg-[rgba(10,22,40,0.8)] border border-white/5 rounded-xl p-8 backdrop-blur-xl">
        <div className="text-center mb-8">
          <div className="font-display text-xl font-bold tracking-wider">EVE <span className="text-eve-gold">NEXUS</span></div>
          <div className="text-[11px] text-gray-500 tracking-[0.15em] uppercase mt-1">Market Intelligence</div>
        </div>

        <button onClick={handleEveLogin}
          className="w-full py-3 bg-eve-gold text-black font-display text-sm font-semibold rounded-lg tracking-wider hover:bg-[#d4b35a] transition-colors mb-4">
          EVE SSO 登录
        </button>

        <div className="flex items-center gap-4 my-4">
          <div className="flex-1 h-px bg-white/10" />
          <span className="text-xs text-gray-500">或</span>
          <div className="flex-1 h-px bg-white/10" />
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <input type="email" placeholder="邮箱" value={email} onChange={e => setEmail(e.target.value)}
            className="w-full p-3 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200 placeholder:text-gray-500 focus:border-eve-gold focus:outline-none" />
          <input type="password" placeholder="密码" value={password} onChange={e => setPassword(e.target.value)}
            className="w-full p-3 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200 placeholder:text-gray-500 focus:border-eve-gold focus:outline-none" />
          <button type="submit"
            className="w-full py-3 bg-white/10 border border-white/10 text-gray-300 font-display text-sm rounded-lg tracking-wider hover:bg-white/15 transition-colors">
            登录
          </button>
        </form>
      </div>
    </div>
  )
}
