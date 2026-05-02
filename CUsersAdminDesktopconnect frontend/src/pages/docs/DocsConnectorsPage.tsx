import { DocsShell } from '../../components/DocsShell'

export function DocsConnectorsPage() {
  return (
    <DocsShell
      title="Connectors only matter if they remain visible and accountable."
      description="IMOS keeps messaging, workflow, social, deployment, and trigger surfaces tied to one runtime so their behavior stays debuggable and operator-visible."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          IMOS supports messaging, workflow, social, productivity, deployment, payment, meeting, and custom API
          surfaces including Telegram, Slack, Discord, WhatsApp, Teams, GitHub, Notion, Airtable, Zapier, Make,
          Vercel, Stripe, Zoom, and generic webhooks.
        </p>
        <p>
          Workflows and scheduled jobs can also inject prompts into sessions without direct human intervention.
          Connectors are useful only if they map cleanly into sessions and visible runtime state.
        </p>
      </div>
    </DocsShell>
  )
}
