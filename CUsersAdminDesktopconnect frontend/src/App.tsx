import { SignInButton, useAuth, useUser } from '@clerk/react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthCliPage } from './pages/AuthCliPage'
import { SiteHeader } from './components/SiteHeader'
import { AboutPage } from './pages/AboutPage'
import { ChangelogPage } from './pages/ChangelogPage'
import { DocsPage } from './pages/DocsPage'
import { HomePage } from './pages/HomePage'
import { IntegrationsPage } from './pages/IntegrationsPage'
import { LaunchPage } from './pages/LaunchPage'
import { PlatformPage } from './pages/PlatformPage'
import { DocsAuthenticationPage } from './pages/docs/DocsAuthenticationPage'
import { DocsConnectorsPage } from './pages/docs/DocsConnectorsPage'
import { DocsDashboardPage } from './pages/docs/DocsDashboardPage'
import { DocsInstallationPage } from './pages/docs/DocsInstallationPage'
import { DocsOperationsPage } from './pages/docs/DocsOperationsPage'
import { DocsOverviewPage } from './pages/docs/DocsOverviewPage'
import { DocsRuntimePage } from './pages/docs/DocsRuntimePage'

const dashboardUrl = import.meta.env.VITE_CONNECT_DASHBOARD_URL || 'http://127.0.0.1:18890'

function Footer() {
  const { isSignedIn } = useAuth()
  const { user } = useUser()

  return (
    <footer className="border-t border-white/8 bg-[#070707] px-5 py-16">
      <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[1.2fr_0.8fr]">
        <div>
          <div className="font-['YDYoonche_M','IBM_Plex_Sans',sans-serif] text-2xl tracking-[0.18em] text-white">CONNECT</div>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-neutral-400">
            Operator-grade AI infrastructure with one public frontend, one authenticated control plane, and one runtime that actually executes work across tools, sessions, memory, and channels.
          </p>
          <div className="mt-6 flex flex-wrap gap-3 text-xs uppercase tracking-[0.18em] text-neutral-500">
            <span>Gateway</span>
            <span>Runtime</span>
            <span>Canvas</span>
            <span>Messaging</span>
            <span>Automation</span>
          </div>
        </div>
        <div className="grid gap-8 sm:grid-cols-2">
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-neutral-500">Explore</div>
            <div className="mt-4 grid gap-3 text-sm text-neutral-300">
              <a href="/about" className="transition hover:text-white">About</a>
              <a href="/platform" className="transition hover:text-white">Platform</a>
              <a href="/integrations" className="transition hover:text-white">Integrations</a>
              <a href="/docs" className="transition hover:text-white">Docs</a>
              <a href="/changelog" className="transition hover:text-white">Changelog</a>
              <a href="/launch" className="transition hover:text-white">Launch</a>
            </div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-neutral-500">Access</div>
            <div className="mt-4 flex flex-col items-start gap-3">
              {!isSignedIn ? (
                <SignInButton mode="modal">
                  <button className="rounded-full border border-white/10 px-4 py-2 text-sm text-neutral-200 transition hover:border-[#27F3A9]/50 hover:text-white">
                    Sign in
                  </button>
                </SignInButton>
              ) : (
                <div className="rounded-full border border-[#27F3A9]/25 px-4 py-2 text-sm text-[#9af6d0]">
                  Signed in as {user?.primaryEmailAddress?.emailAddress || user?.id}
                </div>
              )}
              <a
                href={dashboardUrl}
                target="_blank"
                rel="noreferrer"
                className="rounded-full bg-[#27F3A9] px-4 py-2 text-sm font-medium text-black transition hover:brightness-110"
              >
                Open Operator
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-black text-white">
        <SiteHeader dashboardUrl={dashboardUrl} />
        <Routes>
          <Route path="/" element={<HomePage dashboardUrl={dashboardUrl} />} />
          <Route path="/auth/cli" element={<AuthCliPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/platform" element={<PlatformPage />} />
          <Route path="/integrations" element={<IntegrationsPage />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/docs/overview" element={<DocsOverviewPage />} />
          <Route path="/docs/installation" element={<DocsInstallationPage />} />
          <Route path="/docs/authentication" element={<DocsAuthenticationPage />} />
          <Route path="/docs/runtime" element={<DocsRuntimePage />} />
          <Route path="/docs/dashboard" element={<DocsDashboardPage />} />
          <Route path="/docs/connectors" element={<DocsConnectorsPage />} />
          <Route path="/docs/operations" element={<DocsOperationsPage />} />
          <Route path="/changelog" element={<ChangelogPage />} />
          <Route path="/launch" element={<LaunchPage />} />
        </Routes>
        <Footer />
      </div>
    </BrowserRouter>
  )
}
