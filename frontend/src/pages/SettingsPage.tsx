import { useState } from 'react'

type Tab = 'llm' | 'notifications' | 'risk' | 'characters'

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>('llm')

  const tabs: { key: Tab; label: string }[] = [
    { key: 'llm', label: 'LLM 配置' },
    { key: 'notifications', label: '通知设置' },
    { key: 'risk', label: '风险参数' },
    { key: 'characters', label: '角色管理' },
  ]

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-lg font-semibold tracking-wider">系统配置</h1>
      <div className="flex gap-6">
        <div className="w-48 flex flex-col gap-1">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`text-left px-4 py-2.5 rounded-lg text-sm transition-colors ${
                tab === t.key ? 'bg-eve-gold/10 text-eve-gold border border-eve-gold/30' : 'text-gray-400 hover:text-gray-200'
              }`}>{t.label}</button>
          ))}
        </div>
        <div className="flex-1 bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm max-w-lg">
          {tab === 'llm' && (
            <div className="space-y-4">
              <h3 className="font-display text-sm font-semibold">LLM 供应商</h3>
              <select className="w-full p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200">
                <option>Anthropic</option><option>OpenAI</option><option>DeepSeek</option><option>Ollama (本地)</option>
              </select>
              <div><label className="text-xs text-gray-500">API Key</label>
                <input type="password" placeholder="sk-..." className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" /></div>
              <p className="text-[11px] text-gray-500">每个 Agent 可独立配置模型。API Key 加密存储。扫描用便宜模型节省费用，分析用强模型保证质量。</p>
            </div>
          )}
          {tab === 'notifications' && <p className="text-sm text-gray-400">通知渠道配置（站内/邮件/Discord）</p>}
          {tab === 'risk' && (
            <div className="space-y-4">
              <div><label className="text-xs text-gray-500">风险偏好</label>
                <select className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200">
                  <option>保守</option><option>适中</option><option>激进</option></select></div>
              <div><label className="text-xs text-gray-500">最小利润率 (%)</label>
                <input type="number" defaultValue={5} className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" /></div>
              <div><label className="text-xs text-gray-500">单次最大仓位 (%)</label>
                <input type="number" defaultValue={10} className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" /></div>
            </div>
          )}
          {tab === 'characters' && <p className="text-sm text-gray-400">EVE 角色绑定管理（SSO Token 状态）</p>}
        </div>
      </div>
    </div>
  )
}
