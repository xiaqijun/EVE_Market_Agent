import { useState } from 'react'

const mockTrades = [
  { id: '1', item: '三钛合金', type: '买入', quantity: '500,000', price: '5.20 ISK', total: '2,600,000 ISK', date: '2026-05-26', profit: '—' },
  { id: '2', item: '三钛合金', type: '卖出', quantity: '500,000', price: '5.85 ISK', total: '2,925,000 ISK', date: '2026-05-27', profit: '+325,000 ISK' },
]

export default function TradesPage() {
  const [showAdd, setShowAdd] = useState(false)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-lg font-semibold tracking-wider">交易记录</h1>
        <button onClick={() => setShowAdd(!showAdd)}
          className="px-4 py-2 bg-eve-gold text-black font-display text-xs font-semibold rounded-lg tracking-wider">新增交易</button>
      </div>

      <div className="bg-eve-card border border-white/5 rounded-xl overflow-hidden backdrop-blur-sm">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-white/5 text-left text-[11px] text-gray-500 font-display tracking-wider">
            <th className="p-4">物品</th><th className="p-4">类型</th><th className="p-4">数量</th><th className="p-4">单价</th><th className="p-4">总价</th><th className="p-4">日期</th><th className="p-4">盈亏</th>
          </tr></thead>
          <tbody>
            {mockTrades.map(t => (
              <tr key={t.id} className="border-b border-white/5 hover:bg-white/[0.02] text-gray-300">
                <td className="p-4">{t.item}</td><td className="p-4">{t.type}</td><td className="p-4">{t.quantity}</td><td className="p-4">{t.price}</td><td className="p-4">{t.total}</td><td className="p-4">{t.date}</td>
                <td className={`p-4 font-display ${t.profit.startsWith('+') ? 'text-eve-profit' : 'text-gray-500'}`}>{t.profit}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showAdd && (
        <div className="bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
          <h3 className="font-display text-sm font-semibold mb-4">记录新交易</h3>
          <div className="grid grid-cols-2 gap-4">
            <input placeholder="物品名称" className="p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" />
            <input placeholder="数量" type="number" className="p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" />
            <input placeholder="单价" type="number" className="p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" />
            <input placeholder="总价" type="number" className="p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" />
            <button className="col-span-2 py-2.5 bg-eve-gold text-black font-display text-xs font-semibold rounded-lg">保存</button>
          </div>
        </div>
      )}
    </div>
  )
}
