import { NavLink } from 'react-router-dom'

export type DocItem = {
  path: string
  label: string
}

type DocSidebarProps = {
  items: DocItem[]
}

export function DocSidebar({ items }: DocSidebarProps) {
  return (
    <aside className="min-h-0 overflow-y-auto border-r border-[#1d1a14] bg-[#080706] px-3 py-5 sm:px-4 sm:py-6">
      <div className="sticky top-0 z-10 bg-[#080706] pb-4 text-[11px] uppercase tracking-[0.22em] text-neutral-500">
        Documentation
      </div>
      <nav className="mt-5 grid gap-2">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `rounded-2xl px-3 py-2 text-xs leading-5 transition sm:text-sm ${
                isActive
                  ? 'bg-white/[0.05] text-white'
                  : 'text-neutral-400 hover:bg-white/[0.03] hover:text-white'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
