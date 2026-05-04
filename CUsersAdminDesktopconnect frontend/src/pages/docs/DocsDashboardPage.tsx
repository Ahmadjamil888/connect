import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

export function DocsDashboardPage() {
  return (
    <DocsShell
      title="Operator Dashboard"
      description="The dashboard is the browser-side operator control plane for chat, shell, voice, sessions, integrations, workflows, and live activity."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          The dashboard is the CLI companion for IMOS: live chat, shell access, voice controls, session visibility,
          connection setup, workflow management, configuration forms, and runtime activity from one operator surface.
        </p>
        <CodeBlock label="Open the dashboard" code={'imos dashboard'} />
        <CodeBlock
          label="Useful dashboard-linked commands"
          code={`imos
/dashboard
/status
/doctor
/session list
/listen status
/voice test`}
        />
      </div>
    </DocsShell>
  )
}
