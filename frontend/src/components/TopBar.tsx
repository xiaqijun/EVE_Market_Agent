export default function TopBar() {
  return (
    <header className="h-[60px] bg-[rgba(6,16,36,0.8)] border-b border-white/5 backdrop-blur-xl flex items-center justify-between px-8 sticky top-0 z-5">
      <div className="flex items-center gap-4">
        <h1 className="font-display text-lg font-semibold tracking-wider">指挥中心</h1>
        <div className="flex items-center gap-1.5 text-[11px] text-eve-cyan">
          <span className="w-1.5 h-1.5 rounded-full bg-eve-cyan shadow-[0_0_8px_rgba(0,180,216,0.4)] animate-pulse" />
          系统在线 · 上次扫描 3 分钟前
        </div>
      </div>
      <div className="flex items-center gap-5">
        <div className="text-right"><div className="font-display text-sm font-semibold text-eve-gold">24.5 亿 ISK</div><div className="text-[10px] text-gray-500 tracking-wider">净资产估值</div></div>
        <button className="w-10 h-10 rounded-full bg-white/5 border border-white/5 flex items-center justify-center relative text-lg hover:border-eve-gold hover:shadow-[0_0_12px_rgba(201,168,76,0.3)] transition-all">
          🔔<span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-eve-danger" />
        </button>
      </div>
    </header>
  )
}
