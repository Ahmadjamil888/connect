import { SectionBlock } from '../components/SectionBlock'

const integrationGroups = {
  Messaging: ['Telegram', 'Slack webhooks', 'Slack bot mode', 'Discord webhooks', 'Twilio WhatsApp'],
  Automation: ['Cron jobs', 'Workflow webhooks', 'Background orchestration', 'Session routing'],
  Operator: ['Dashboard', 'Node pairing', 'Canvas persistence', 'CLI and browser auth handoff'],
}

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
              <ul className="mt-4 space-y-2 text-sm leading-6 text-neutral-300">
                {items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </SectionBlock>
    </div>
  )
}
