import { SectionBlock } from '../components/SectionBlock'

const integrationGroups = {
  Messaging: ['Telegram', 'Slack webhooks', 'Slack bot mode', 'Discord webhooks', 'Twilio WhatsApp'],
  Automation: ['Cron jobs', 'Workflow webhooks', 'Background orchestration', 'Session routing'],
  Operator: ['Dashboard', 'Node pairing', 'Canvas persistence', 'CLI and browser auth handoff'],
}

const notes = [
  'Connectors matter only if they land in visible sessions and can be traced through the runtime.',
  'Webhook-triggered workflows should behave like first-class runtime inputs rather than detached automations.',
  'Cloud-facing connectors require stricter auth, signing, and deployment review than localhost experiments.',
]

export function IntegrationsPage() {
  return (
    <div className="bg-black pt-8">
      <SectionBlock
        eyebrow="Integrations"
        title="Connectors and operators in one fabric"
        description="The frontend presents the real connector families and operator surfaces with a cleaner structure that matches the product instead of overstating it."
      >
        <div className="grid gap-4 md:grid-cols-3">
          {Object.entries(integrationGroups).map(([group, items]) => (
            <div key={group} className="rounded-[2rem] border border-white/8 bg-[#07120f] p-6">
              <h3 className="text-xl font-medium text-white">{group}</h3>
              <ul className="mt-4 space-y-2 text-sm leading-7 text-neutral-300">
                {items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </SectionBlock>

      <SectionBlock
        eyebrow="Operational notes"
        title="Integrations are only useful when they stay accountable."
        description="CONNECT treats messaging, workflows, and nodes as operator surfaces, not magical black boxes. That means state should remain observable and delivery should remain constrained."
      >
        <div className="grid gap-4">
          {notes.map((note) => (
            <div key={note} className="rounded-[2rem] border border-white/8 bg-white/[0.03] p-6 text-sm leading-7 text-neutral-400">
              {note}
            </div>
          ))}
        </div>
      </SectionBlock>
    </div>
  )
}
