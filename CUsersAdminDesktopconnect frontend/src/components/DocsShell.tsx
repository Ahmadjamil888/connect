import type { ReactNode } from 'react'
import { DocSidebar, type DocItem } from './DocSidebar'

export const DOC_ITEMS: DocItem[] = [
  { path: '/docs/overview', label: 'Overview' },
  { path: '/docs/installation', label: 'Installation' },
  { path: '/docs/authentication', label: 'Authentication' },
  { path: '/docs/runtime', label: 'Gateway and Runtime' },
  { path: '/docs/dashboard', label: 'Dashboard' },
  { path: '/docs/connectors', label: 'Messaging and Connectors' },
  { path: '/docs/operations', label: 'Operations' },
]

type DocsShellProps = {
  title: string
  description: string
  children: ReactNode
}

export function DocsShell({ title, description, children }: DocsShellProps) {
  return (
    <div className="bg-black pt-8">
      <section className="border-b border-white/8 px-5 py-20">
        <div className="mx-auto max-w-7xl">
          <div className="text-xs uppercase tracking-[0.22em] text-[#27F3A9]">Documentation</div>
          <h1 className="mt-4 max-w-4xl text-4xl font-light tracking-[-0.05em] text-white md:text-6xl">{title}</h1>
          <p className="mt-6 max-w-3xl text-base leading-8 text-neutral-400">{description}</p>
        </div>
      </section>

      <section className="px-5 py-16">
        <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[260px_minmax(0,1fr)]">
          <DocSidebar items={DOC_ITEMS} />
          <div className="rounded-[2rem] border border-white/8 bg-[#070707] p-8 md:p-10">{children}</div>
        </div>
      </section>
    </div>
  )
}
