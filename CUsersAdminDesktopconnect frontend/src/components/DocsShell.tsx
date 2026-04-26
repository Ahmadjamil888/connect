import { SignInButton, SignUpButton, UserButton, useAuth } from '@clerk/react'
import { useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
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
  const { isSignedIn } = useAuth()
  const [query, setQuery] = useState('')

  const filteredItems = useMemo(() => {
    const value = query.trim().toLowerCase()
    if (!value) return DOC_ITEMS
    return DOC_ITEMS.filter((item) => item.label.toLowerCase().includes(value))
  }, [query])

  return (
    <div className="min-h-screen bg-black text-white">
      <header className="sticky top-0 z-50 border-b border-[#1d1a14] bg-black/92 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-3 px-4 py-4 sm:px-5">
          <Link to="/" className="shrink-0 font-['YDYoonche_M','IBM_Plex_Sans',sans-serif] text-lg tracking-[0.28em] text-white">
            CONNECT
          </Link>

          <div className="mx-2 hidden max-w-2xl flex-1 md:block">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search documentation"
              className="w-full rounded-full border border-white/10 bg-[#0f0d0a] px-5 py-3 text-sm text-white outline-none transition placeholder:text-neutral-500 focus:border-[#27F3A9]/40"
            />
          </div>

          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            {!isSignedIn ? (
              <>
                <SignInButton mode="modal">
                  <button className="rounded-full border border-white/10 px-4 py-2 text-sm text-neutral-200 transition hover:border-[#27F3A9]/50 hover:text-white">
                    Sign in
                  </button>
                </SignInButton>
                <SignUpButton mode="modal">
                  <button className="rounded-full bg-[#27F3A9] px-4 py-2 text-sm font-medium text-black transition hover:brightness-110">
                    Sign up
                  </button>
                </SignUpButton>
              </>
            ) : (
              <UserButton
                appearance={{
                  elements: {
                    avatarBox: 'h-10 w-10',
                  },
                }}
              />
            )}
          </div>
        </div>

        <div className="mx-auto px-4 pb-4 md:hidden sm:px-5">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search documentation"
            className="w-full rounded-full border border-white/10 bg-[#0f0d0a] px-5 py-3 text-sm text-white outline-none transition placeholder:text-neutral-500 focus:border-[#27F3A9]/40"
          />
        </div>
      </header>

      <section className="border-b border-[#1d1a14] px-4 py-14 sm:px-5 md:py-18">
        <div className="mx-auto max-w-[1500px]">
          <div className="text-xs uppercase tracking-[0.22em] text-[#27F3A9]">Documentation</div>
          <h1 className="mt-4 max-w-4xl text-4xl font-light tracking-[-0.05em] text-white md:text-6xl">{title}</h1>
          <p className="mt-6 max-w-3xl text-base leading-8 text-neutral-400">{description}</p>
        </div>
      </section>

      <section className="px-4 py-10 sm:px-5 md:py-12">
        <div className="mx-auto grid max-w-[1500px] gap-8 xl:grid-cols-[280px_minmax(0,1fr)]">
          <DocSidebar items={filteredItems} />
          <div className="min-h-[60vh] rounded-[2rem] border border-[#1d1a14] bg-[#0b0a08] p-6 sm:p-8 md:p-10">{children}</div>
        </div>
      </section>
    </div>
  )
}
