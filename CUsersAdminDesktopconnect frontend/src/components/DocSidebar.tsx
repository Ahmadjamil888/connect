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
    <aside className="top-24 h-fit rounded-[2rem] border border-white/8 bg-[#080808] p-5 lg:sticky">
      <div className="text-xs uppercase tracking-[0.22em] text-neutral-500">Documentation</div>
      <nav className="mt-5 grid gap-2">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `rounded-2xl px-3 py-2 text-sm transition ${
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
