export default function PortfolioPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-lg font-semibold tracking-wider">资产总览</h1>
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: '总资产估值', value: '24.5 亿 ISK', color: 'text-eve-cyan' },
          { label: '可用 ISK', value: '8.2 亿 ISK', color: 'text-eve-profit' },
          { label: '持仓市值', value: '16.3 亿 ISK', color: 'text-eve-gold' },
        ].map(s => (
          <div key={s.label} className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm text-center">
            <div className="text-[11px] text-gray-500 font-display tracking-wider mb-2">{s.label}</div>
            <div className={`font-display text-2xl font-bold ${s.color}`}>{s.value}</div>
          </div>
        ))}
      </div>
      <div className="bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
        <h3 className="font-display text-[13px] font-semibold tracking-wider mb-4">盈亏走势（近 30 天）</h3>
        <div className="h-48 flex items-end gap-1.5">
          {[55, 70, 40, 65, 80, 60, 35, 75, 90, 70, 45, 85, 50, 95, 65, 30, 55, 100, 80, 70].map((h, i) => (
            <div key={i} className="flex-1 rounded-t-sm transition-all hover:brightness-125 hover:scale-y-105 origin-bottom"
              style={{ height: `${h}%`, background: h > 50 ? 'linear-gradient(180deg, #2ecc71, rgba(46,204,113,0.2))' : 'linear-gradient(180deg, #e74c3c, rgba(231,76,60,0.2))' }} />
          ))}
        </div>
      </div>
    </div>
  )
}
