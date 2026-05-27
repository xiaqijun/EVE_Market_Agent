import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

const API = '/api/v1'

export default function LoginPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const setAuth = useAuthStore(s => s.setAuth)
  const navigate = useNavigate()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const url = mode === 'login' ? `${API}/auth/login` : `${API}/auth/register`
      const body = mode === 'login'
        ? { email, password }
        : { email, password, display_name: name || email.split('@')[0] }
      const res = await fetch(url, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || data.message || '操作失败')
        return
      }
      setAuth(data.access_token, data.user)
      navigate('/')
    } catch {
      setError('网络错误，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  const [eveSsoAvailable, setEveSsoAvailable] = useState(true)

  const handleEveLogin = async () => {
    setError('')
    try {
      const res = await fetch(`${API}/auth/eve/login`)
      if (res.status === 503) {
        setEveSsoAvailable(false)
        setError('EVE SSO 未配置，请使用邮箱登录')
        return
      }
      const data = await res.json()
      if (data.url) {
        window.location.href = data.url
      } else {
        setError('EVE SSO 配置异常')
      }
    } catch {
      setError('连接服务器失败')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#020810]">
      <div className="w-[420px] bg-[rgba(10,22,40,0.9)] border border-white/10 rounded-xl p-8 backdrop-blur-xl shadow-2xl">
        <div className="text-center mb-8">
          <div className="font-display text-2xl font-bold tracking-wider">EVE <span className="text-eve-gold">NEXUS</span></div>
          <div className="text-[11px] text-gray-400 tracking-[0.15em] uppercase mt-2">EVE 市场智能助手</div>
        </div>

        {eveSsoAvailable ? (
          <button onClick={handleEveLogin}
            className="w-full py-3.5 bg-gradient-to-r from-eve-gold to-[#d4a84c] text-black font-display text-sm font-semibold rounded-lg tracking-wider hover:brightness-110 transition-all flex items-center justify-center gap-2">
            <span className="text-lg">◎</span> 使用 EVE 账号登录
          </button>
        ) : (
          <div className="w-full py-3 bg-white/5 border border-white/10 rounded-lg text-center text-sm text-gray-400">
            EVE SSO 未配置（需在服务器 .env 设置 ESI_CLIENT_ID）
          </div>
        )}

        <div className="flex items-center gap-4 my-5">
          <div className="flex-1 h-px bg-white/10" />
          <span className="text-xs text-gray-500">或使用邮箱</span>
          <div className="flex-1 h-px bg-white/10" />
        </div>

        <div className="flex gap-2 mb-4">
          <button onClick={() => { setMode('login'); setError('') }}
            className={`flex-1 py-2 text-xs font-display rounded-lg transition-colors ${mode === 'login' ? 'bg-eve-gold/10 text-eve-gold border border-eve-gold/30' : 'bg-white/5 text-gray-400 border border-white/5'}`}>
            登录
          </button>
          <button onClick={() => { setMode('register'); setError('') }}
            className={`flex-1 py-2 text-xs font-display rounded-lg transition-colors ${mode === 'register' ? 'bg-eve-gold/10 text-eve-gold border border-eve-gold/30' : 'bg-white/5 text-gray-400 border border-white/5'}`}>
            注册
          </button>
        </div>

        <form onSubmit={handleLogin} className="space-y-3">
          {mode === 'register' && (
            <input type="text" placeholder="显示名称" value={name} onChange={e => setName(e.target.value)}
              className="w-full p-3 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200 placeholder:text-gray-500 focus:border-eve-gold focus:outline-none" />
          )}
          <input type="email" placeholder="邮箱地址" value={email} onChange={e => setEmail(e.target.value)}
            className="w-full p-3 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200 placeholder:text-gray-500 focus:border-eve-gold focus:outline-none" />
          <input type="password" placeholder="密码" value={password} onChange={e => setPassword(e.target.value)}
            className="w-full p-3 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200 placeholder:text-gray-500 focus:border-eve-gold focus:outline-none" />

          {error && <div className="text-xs text-eve-danger bg-eve-danger/10 border border-eve-danger/20 rounded-lg p-2">{error}</div>}

          <button type="submit" disabled={loading}
            className="w-full py-3 bg-white/10 border border-white/10 text-gray-200 font-display text-sm font-semibold rounded-lg tracking-wider hover:bg-white/15 disabled:opacity-50 transition-all">
            {loading ? '处理中...' : mode === 'login' ? '登录' : '注册'}
          </button>
        </form>

        <div className="mt-4 text-center text-[10px] text-gray-600">
          {mode === 'login' ? '还没有账号？' : '已有账号？'}
          <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
            className="text-eve-gold hover:underline ml-1">
            {mode === 'login' ? '注册新账号' : '去登录'}
          </button>
        </div>
      </div>
    </div>
  )
}
