export default function Dashboard() {
  return (
    <div className="flex flex-col gap-6">
      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: '活跃套利机会', value: '12', color: 'text-eve-cyan', change: '▲ 3 个新机会' },
          { label: '投资推荐', value: '5', color: 'text-eve-gold', change: '▲ 2 个强烈推荐' },
          { label: '本月已实现盈亏', value: '+12.5 亿', color: 'text-eve-profit', change: '▲ 胜率 83% · 12 笔' },
          { label: 'AI 信心指数', value: '87%', color: 'text-eve-cyan', change: '基于 156 次历史推荐' },
        ].map(s => (
          <div key={s.label} className="relative bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm overflow-hidden hover:border-white/10 transition-all">
            <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
            <div className="text-[11px] text-gray-500 tracking-[0.08em] uppercase font-display mb-2">{s.label}</div>
            <div className={`font-display text-[28px] font-bold tracking-wider ${s.color}`}>{s.value}</div>
            <div className="text-xs text-eve-profit mt-1.5">{s.change}</div>
          </div>
        ))}
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-2 gap-4">
        <Panel title="◆ 套利扫描结果">
          <div className="text-sm text-gray-400 p-8 text-center">Scanner Agent 就绪，等待扫描任务...</div>
        </Panel>
        <Panel title="◆ 投资分析">
          <div className="text-sm text-gray-400 p-8 text-center">Analyst Agent 就绪，等待分析任务...</div>
        </Panel>
        <Panel title="◆ 盈亏走势（近 30 天）">
          <div className="text-sm text-gray-400 p-8 text-center">暂无交易数据</div>
        </Panel>
        <Panel title="◆ AI 助手状态">
          <div className="text-sm text-gray-400 p-8 text-center">所有 Agent 在线 · LLM: 已连接</div>
        </Panel>
      </div>
    </div>
  )
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-eve-card border border-white/5 rounded-xl backdrop-blur-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
        <h3 className="font-display text-[13px] font-semibold tracking-[0.06em]">{title}</h3>
        <span className="text-[11px] text-eve-gold font-display tracking-wider cursor-pointer hover:opacity-70">查看全部 →</span>
      </div>
      {children}
    </div>
  )
}
