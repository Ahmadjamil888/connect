import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

export function DocsDashboardPage() {
  return (
    <DocsShell
      title="The dashboard is the live IMOS operator surface."
      description="It exposes chat, shell, voice, models, API keys, integrations, workflows, and activity in one orange-and-black control plane."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          The current dashboard is the classic IMOS control room: live chat, full shell access, voice controls,
          connection setup, multi-step workflows, and local activity visibility without exposing internal launch files.
        </p>
        <CodeBlock label="Open the dashboard" code={'imos dashboard'} />
        <CodeBlock
          label="Useful dashboard-linked commands"
          code={`imos
imos status
imos adapters list
imos wake status
imos palette set --shell ember --dashboard ember`}
        />
      </div>
    </DocsShell>
  )
}
