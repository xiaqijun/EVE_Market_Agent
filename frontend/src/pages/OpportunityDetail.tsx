import { useParams } from 'react-router-dom'

export default function OpportunityDetail() {
  const { id } = useParams()

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-4">
        <button onClick={() => window.history.back()} className="font-display text-xs text-eve-gold tracking-wider hover:opacity-70">← 返回列表</button>
        <h1 className="font-display text-lg font-semibold tracking-wider">机会详情</h1>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-4">价格信息</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between"><span className="text-gray-400">买入价 (Jita)</span><span className="font-display">5.20 ISK</span></div>
            <div className="flex justify-between"><span className="text-gray-400">卖出价 (Amarr)</span><span className="font-display text-eve-profit">5.85 ISK</span></div>
            <div className="flex justify-between"><span className="text-gray-400">原始价差</span><span className="font-display text-eve-cyan">+12.5%</span></div>
            <div className="flex justify-between"><span className="text-gray-400">净利润率</span><span className="font-display text-eve-profit">+8.2%</span></div>
          </div>
        </div>

        <div className="bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-4">成本分解</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between"><span className="text-gray-400">中介费</span><span>0.03 ISK/单位</span></div>
            <div className="flex justify-between"><span className="text-gray-400">销售税</span><span>0.05 ISK/单位</span></div>
            <div className="flex justify-between"><span className="text-gray-400">估算运费</span><span>0.12 ISK/单位</span></div>
            <div className="flex justify-between"><span className="text-gray-400">资金成本</span><span>0.02 ISK/单位</span></div>
          </div>
        </div>

        <div className="col-span-2 bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-4">AI 分析报告</h3>
          <div className="text-sm text-gray-300 leading-relaxed space-y-3">
            <p>三钛合金在 Jita ↔ Amarr 航线显示稳定的套利空间。当前成交量充足（日均 1,200M 单位），流动性风险低。</p>
            <p><strong className="text-eve-profit">推荐操作：</strong>建议分批买入，每批不超过日成交量的 5%，降低滑点影响。</p>
            <p><strong className="text-eve-warning">风险提示：</strong>关注版本更新对矿物市场的影响。以上分析基于历史数据，实际结果可能不同。</p>
          </div>
        </div>

        <div className="col-span-2 flex gap-3">
          <button className="px-6 py-2.5 bg-eve-profit/20 border border-eve-profit/30 text-eve-profit font-display text-xs rounded-lg tracking-wider hover:bg-eve-profit/30 transition-colors">追踪此机会</button>
          <button className="px-6 py-2.5 bg-white/5 border border-white/10 text-gray-400 font-display text-xs rounded-lg tracking-wider hover:bg-white/10 transition-colors">标记已交易</button>
          <button className="px-6 py-2.5 bg-white/5 border border-white/10 text-gray-400 font-display text-xs rounded-lg tracking-wider hover:bg-white/10 transition-colors ml-auto">忽略</button>
        </div>
      </div>
    </div>
  )
}
