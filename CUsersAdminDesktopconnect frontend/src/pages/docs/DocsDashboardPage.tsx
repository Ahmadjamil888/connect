import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

export function DocsDashboardPage() {
  return (
    <DocsShell
      title="The dashboard is the live status surface for the runtime."
      description="It exposes sessions, memory, tools, nodes, canvas state, and a quick-ask panel so operators can observe and direct the system without dropping into internals."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          Users can open the operator dashboard through the site, through the CLI, or as part of a background stack. In
          cloud mode, the dashboard binding and authentication policy should be reviewed before exposing it publicly.
        </p>
        <CodeBlock label="Run the dashboard locally" code={'connect dashboard'} />
        <CodeBlock label="Run the dashboard in cloud bind mode" code={'connect dashboard --cloud'} />
      </div>
    </DocsShell>
  )
}
