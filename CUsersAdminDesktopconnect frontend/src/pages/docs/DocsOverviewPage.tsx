import { DocsShell } from '../../components/DocsShell'

export function DocsOverviewPage() {
  return (
    <DocsShell
      title="Everything needed to install, authenticate, operate, and extend IMOS."
      description="This section is split into focused pages so operators can move directly to shell, dashboard, integrations, and workflow control without exposing internal runtime entry files."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          IMOS combines a public frontend, a signed-in operator entry flow, a local dashboard, and one runtime that can
          route work across models, apps, messaging platforms, workflows, shell execution, browser actions, and local
          machine control.
        </p>
        <p>
          The frontend is intentionally separate from the runtime. That lets you host the site publicly, handle sign-in,
          and then bridge the user into the local IMOS dashboard only when they are ready to operate the system.
        </p>
        <p>
          The backend is where actual work happens. It owns the shell, dashboard, orchestration jobs, messaging
          connectors, workflow triggers, voice layer, adapter registry, and the local session established after
          verification.
        </p>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            ['Public frontend', 'Landing pages, docs, sign-in, and the browser-facing product surface.'],
            ['Operator backend', 'Shell, dashboard, adapters, workflows, voice, memory, sessions, and service mode.'],
            ['Identity bridge', 'Verified sign-in and local operator session handoff into the IMOS shell or dashboard.'],
          ].map(([title, text]) => (
            <div key={title} className="rounded-[1.6rem] border border-white/8 bg-white/[0.03] p-5">
              <h2 className="text-xl text-white">{title}</h2>
              <p className="mt-3 text-sm leading-7 text-neutral-400">{text}</p>
            </div>
          ))}
        </div>
      </div>
    </DocsShell>
  )
}
