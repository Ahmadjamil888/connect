import { DocsShell } from '../../components/DocsShell'

export function DocsRuntimePage() {
  return (
    <DocsShell
      title="The gateway routes. The runtime thinks and executes."
      description="The product is deliberately split so the execution model remains consistent whether you launch locally, expose cloud mode, or run the dashboard stack."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          The gateway acts as the control plane. It accepts routed requests, session traffic, connector payloads, and
          workflow triggers, then passes them into the runtime.
        </p>
        <p>
          The runtime assembles context, invokes the configured model provider, filters tools by policy, persists session
          state, stores memory, and delivers outputs back into the correct surface.
        </p>
        <p>
          This separation makes it possible to run the system locally, expose it in cloud mode, or start it through the
          dashboard stack or Windows service layer without changing the core execution model.
        </p>
      </div>
    </DocsShell>
  )
}
