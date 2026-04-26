import { SignInButton, SignUpButton, UserButton, useAuth } from '@clerk/react'
import { Link, NavLink } from 'react-router-dom'

type SiteHeaderProps = {
  dashboardUrl: string
}

const NAV_ITEMS = [
  { to: '/', label: 'Home' },
  { to: '/about', label: 'About' },
  { to: '/platform', label: 'Platform' },
  { to: '/integrations', label: 'Integrations' },
  { to: '/docs', label: 'Docs' },
  { to: '/changelog', label: 'Changelog' },
  { to: '/launch', label: 'Launch' },
]

export function SiteHeader({ dashboardUrl }: SiteHeaderProps) {
  const { isSignedIn } = useAuth()

  return (
    <header className="sticky top-0 z-50 border-b border-white/8 bg-black/82 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-4 py-4 sm:px-5">
        <div className="flex items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-3">
          <div className="font-['YDYoonche_M','IBM_Plex_Sans',sans-serif] text-lg tracking-[0.28em] text-white">
            CONNECT
          </div>
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `text-sm transition-colors ${isActive ? 'text-white' : 'text-neutral-500 hover:text-neutral-200'}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          <a
            href={dashboardUrl}
            target="_blank"
            rel="noreferrer"
            className="hidden rounded-full border border-white/10 px-4 py-2 text-sm text-neutral-200 transition hover:border-[#27F3A9]/50 hover:text-white md:inline-flex"
          >
            Open Operator
          </a>
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

        <nav className="mt-4 flex gap-2 overflow-x-auto pb-1 md:hidden">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `shrink-0 rounded-full border px-3 py-2 text-xs transition ${
                  isActive
                    ? 'border-[#27F3A9]/35 bg-[#09120f] text-white'
                    : 'border-white/8 text-neutral-400 hover:border-white/14 hover:text-white'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
