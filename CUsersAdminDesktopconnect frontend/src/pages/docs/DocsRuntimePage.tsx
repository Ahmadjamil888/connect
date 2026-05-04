import { DocsShell } from '../../components/DocsShell'

export function DocsRuntimePage() {
  return (
    <DocsShell
      title="Routing and Runtime"
      description="The gateway routes work, the runtime executes it, and the shell plus dashboard remain consistent whether you launch locally or expose the system through additional surfaces."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          The gateway acts as the control plane. It accepts routed requests, session traffic, connector payloads, and
          workflow triggers, then passes them into the runtime.
        </p>
        <p>
          The runtime assembles context, invokes the configured model provider, filters tools by policy, persists session
          state, stores memory, and delivers outputs back into the correct surface whether that is the CLI shell,
          dashboard, voice layer, or an integration.
        </p>
        <p>
          Routing rules let you assign work types like code, research, writing, or computer control to different
          providers. That keeps the operator surface simple while still giving the runtime a model-aware execution plan.
        </p>
      </div>
    </DocsShell>
  )
}
