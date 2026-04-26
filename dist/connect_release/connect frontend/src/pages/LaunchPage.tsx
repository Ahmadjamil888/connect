import { SectionBlock } from '../components/SectionBlock'

const checklist = [
  'Run the backend with `connect dashboard` or `python ai_assistant.py --dashboard`.',
  'Sign in through Clerk in the frontend or backend login flow.',
  'Use the operator dashboard for sessions, tools, workflows, and runtime status.',
  'Validate Slack and WhatsApp live with `/slack-test` and `/whatsapp-test` in the CLI.',
]

export function LaunchPage() {
  return (
    <div className="bg-black pt-8">
      <SectionBlock
        eyebrow="Launch"
        title="A practical launch path"
        description="This frontend is designed to sit in front of the operator backend. It gives you a public-facing narrative and a controlled sign-in path into the runtime."
      >
        <div className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-8">
          <ol className="space-y-4 text-sm leading-6 text-neutral-300">
            {checklist.map((item, index) => (
              <li key={item} className="flex gap-4">
                <span className="inline-flex h-8 w-8 flex-none items-center justify-center rounded-full border border-[#27F3A9]/30 text-[#27F3A9]">
                  {index + 1}
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ol>
        </div>
      </SectionBlock>
    </div>
  )
}
