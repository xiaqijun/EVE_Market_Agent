import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', label: '指挥中心', icon: '◈' },
  { to: '/opportunities', label: '交易机会', icon: '◆' },
  { to: '/chat', label: '对话助手', icon: '◇' },
  { to: '/portfolio', label: '资产总览', icon: '◎' },
  { to: '/trades', label: '交易记录', icon: '◉' },
  { to: '/settings', label: '系统配置', icon: '⚙' },
]

export default function Sidebar() {
  return (
    <aside className="w-[220px] bg-[rgba(6,16,36,0.95)] border-r border-white/5 backdrop-blur-xl flex flex-col sticky top-0 h-screen z-10 flex-shrink-0">
      <div className="px-6 pt-7 pb-5 border-b border-white/5">
        <div className="font-display text-base font-bold tracking-wider">
          EVE <span className="text-eve-gold">NEXUS</span>
        </div>
        <div className="text-[10px] text-gray-500 tracking-[0.15em] uppercase mt-1">Market Intelligence</div>
      </div>
      <nav className="flex-1 py-3">
        {navItems.map(item => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-6 py-2.5 text-[13px] border-l-2 transition-colors ${
                isActive ? 'text-eve-gold bg-[rgba(201,168,76,0.1)] border-eve-gold' : 'text-gray-400 border-transparent hover:text-gray-200 hover:bg-white/[0.02]'
              }`}
          >
            <span className="w-5 text-center text-[15px]">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-6 py-4 border-t border-white/5 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-eve-gold to-[#a08030] flex items-center justify-center text-xs font-bold">XQ</div>
        <div><div className="text-[13px]">玩家名称</div><div className="text-[10px] text-gray-500">Goonswarm Federation</div></div>
      </div>
    </aside>
  )
}
