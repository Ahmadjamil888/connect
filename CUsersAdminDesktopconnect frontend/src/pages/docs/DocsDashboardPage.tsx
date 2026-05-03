import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

export function DocsDashboardPage() {
  return (
    <DocsShell
      title="The dashboard is the live IMOS operator surface."
      description="It exposes chat, beast-mode routing, shell, voice, sessions, models, integrations, workflows, and activity in one control plane."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          The dashboard is the CLI companion for IMOS: live chat, full shell access, voice controls, session visibility,
          connection setup, multi-step workflows, permission controls, and adapter targeting without exposing internal source filenames.
        </p>
        <CodeBlock label="Open the dashboard" code={'imos dashboard'} />
        <CodeBlock
          label="Useful dashboard-linked commands"
          code={`imos
imos status
imos adapters list
imos sessions list
imos shell --beast
imos wake status
imos palette set --shell ember --dashboard ember`}
        />
      </div>
    </DocsShell>
  )
}
