import { DocsShell } from '../../components/DocsShell'

export function DocsConnectorsPage() {
  return (
    <DocsShell
      title="Connectors only matter if they remain visible and accountable."
      description="CONNECT keeps messaging and trigger surfaces tied to the same gateway and runtime model so their behavior stays debuggable and operator-visible."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          CONNECT supports multiple messaging and trigger surfaces including Telegram, Slack webhooks, Slack bot mode,
          Discord webhooks, and Twilio-style WhatsApp paths.
        </p>
        <p>
          Workflows and scheduled jobs can also inject prompts into sessions without direct human intervention.
          Connectors are useful only if they map cleanly into sessions and visible runtime state.
        </p>
      </div>
    </DocsShell>
  )
}
