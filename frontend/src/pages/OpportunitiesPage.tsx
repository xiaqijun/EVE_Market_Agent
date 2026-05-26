import { useState } from 'react'

export default function OpportunitiesPage() {
  const [filter, setFilter] = useState('all')

  const opportunities = [
    { id: '1', type: 'arbitrage', item: '三钛合金', route: 'Jita IV-4 → Amarr VIII-12', profit: '+8.2%', score: 9, risk: 'low', tag: '强烈推荐', tagColor: 'text-eve-profit bg-eve-profit/10 border-eve-profit/30' },
    { id: '2', type: 'arbitrage', item: '类晶体胶矿', route: 'Jita IV-4 → Dodixie IX-20', profit: '+5.1%', score: 7, risk: 'low', tag: '推荐', tagColor: 'text-eve-profit bg-eve-profit/10 border-eve-profit/30' },
    { id: '3', type: 'investment', item: '伊甸币', route: '30天趋势 · RSI 42 · 低于均线', profit: '目标+15%', score: 9, risk: 'medium', tag: '强烈推荐', tagColor: 'text-eve-gold bg-eve-gold/10 border-eve-gold/30' },
    { id: '4', type: 'arbitrage', item: '损伤控制 II', route: 'Amarr VIII-12 → Jita IV-4', profit: '+6.8%', score: 8, risk: 'low', tag: '推荐', tagColor: 'text-eve-profit bg-eve-profit/10 border-eve-profit/30' },
  ]

  const filtered = filter === 'all' ? opportunities : opportunities.filter(o => o.type === filter)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-lg font-semibold tracking-wider">交易机会</h1>
        <div className="flex gap-2">
          {['all', 'arbitrage', 'investment'].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-4 py-1.5 rounded-lg text-xs font-display tracking-wider transition-colors ${
                filter === f ? 'bg-eve-gold text-black' : 'bg-white/5 border border-white/10 text-gray-400 hover:border-white/20'
              }`}>
              {f === 'all' ? '全部' : f === 'arbitrage' ? '套利' : '投资'}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-3">
        {filtered.map(o => (
          <div key={o.id} className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm hover:border-white/10 transition-all flex items-center gap-4">
            <div className="w-9 h-9 rounded-lg bg-eve-cyan/10 text-eve-cyan flex items-center justify-center text-lg flex-shrink-0">
              {o.type === 'arbitrage' ? '⛏' : '💎'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium">{o.item}</div>
              <div className="text-[11px] text-gray-500 mt-0.5">{o.route}</div>
            </div>
            <div className="text-right flex-shrink-0">
              <div className={`font-display text-[15px] font-bold ${o.profit.startsWith('+') ? 'text-eve-profit' : 'text-eve-gold'}`}>{o.profit}</div>
              <div className="text-[11px] text-gray-500 mt-0.5">评分 {o.score}/10 · 风险: {o.risk === 'low' ? '低' : '中'}</div>
            </div>
            <span className={`text-[10px] px-2 py-1 rounded font-display tracking-wider border ${o.tagColor} flex-shrink-0`}>{o.tag}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
