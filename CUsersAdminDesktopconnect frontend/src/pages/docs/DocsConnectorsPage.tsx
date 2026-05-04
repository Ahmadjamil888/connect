import { DocsShell } from '../../components/DocsShell'

export function DocsConnectorsPage() {
  return (
    <DocsShell
      title="Integrations and Connectors"
      description="Messaging, workflow, deployment, and trigger surfaces stay tied to one runtime so their behavior remains visible, debuggable, and operator-controlled."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          IMOS supports messaging, workflow, social, productivity, deployment, payment, meeting, and custom API
          surfaces including Telegram, Slack, Discord, WhatsApp, Teams, Signal, Matrix, Rocket.Chat, Mattermost,
          GitHub, GitLab, Bitbucket, Notion, Airtable, Zapier, Make, Jira, Trello, Linear, Asana, Google Workspace,
          Microsoft 365, Vercel, Netlify, Railway, Render, Stripe, PayPal, Zoom, Google Meet, Calendly, and generic webhooks.
        </p>
        <p>
          Workflows and scheduled jobs can also inject prompts into sessions without direct human intervention.
          Integrations are useful only if they map cleanly into sessions, routing, and visible runtime state.
        </p>
      </div>
    </DocsShell>
  )
}
