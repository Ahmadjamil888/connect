import { DocsShell } from '../../components/DocsShell'

export function DocsOverviewPage() {
  return (
    <DocsShell
      title="Product Overview"
      description="Use these guides to install IMOS, launch the new CLI, open the dashboard, manage routing, and operate the runtime without jumping between internal file-oriented concepts."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          IMOS combines a public frontend, a signed-in operator entry flow, a local dashboard, and one runtime that can
          route work across models, apps, messaging surfaces, workflows, shell execution, browser actions, and local
          machine control.
        </p>
        <p>
          The public site explains the product and handles sign-in. The local runtime owns the actual operator loop:
          the orange CLI shell, the dashboard, voice, sessions, routing, tools, workflows, and machine-side execution.
        </p>
        <p>
          The docs are organized by operator topics instead of implementation filenames. Start with the install guide,
          move into CLI and access setup, then use the dashboard and integrations sections when you are ready to work in
          the live runtime.
        </p>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            ['Public frontend', 'Landing pages, docs, sign-in, and the browser-facing product surface.'],
            ['Operator runtime', 'CLI shell, dashboard, adapters, workflows, voice, memory, sessions, and service mode.'],
            ['Access bridge', 'Verified sign-in and local operator session handoff into the IMOS shell or dashboard.'],
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
