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
    <aside className="top-24 h-fit rounded-[2rem] border border-[#1d1a14] bg-[#080706] p-4 sm:p-5 xl:sticky">
      <div className="text-xs uppercase tracking-[0.22em] text-neutral-500">Documentation</div>
      <nav className="mt-5 flex gap-2 overflow-x-auto pb-1 xl:grid xl:overflow-visible xl:pb-0">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `shrink-0 rounded-2xl px-3 py-2 text-sm transition ${
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
