import { SectionBlock } from '../components/SectionBlock'

const checklist = [
  'Run the backend with `connect dashboard` or `python ai_assistant.py --dashboard`.',
  'Sign in through Clerk in the frontend or by using `connect login` in the CLI.',
  'Use the operator dashboard for sessions, tools, workflows, and runtime status.',
  'Validate live connectors with the CLI test commands once credentials are present.',
]

const phases = [
  {
    title: 'Installation',
    text: 'Install the repo, verify the global launcher path, and confirm `connect --doctor` reports the right repo launcher from any working directory.',
  },
  {
    title: 'Authentication',
    text: 'Ensure Clerk env is present on the frontend and backend, then use the browser-to-localhost handoff flow to establish the local session.',
  },
  {
    title: 'Runtime validation',
    text: 'Confirm provider readiness, dashboard availability, session creation, and at least one working connector path before broad rollout.',
  },
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
          <ol className="space-y-4 text-sm leading-7 text-neutral-300">
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

      <SectionBlock
        eyebrow="Readiness"
        title="Launch is a sequence, not a slogan."
        description="A real launch requires the public site, auth flow, launcher path, runtime health, and connector validation to all agree with each other."
      >
        <div className="grid gap-4 md:grid-cols-3">
          {phases.map((phase) => (
            <article key={phase.title} className="rounded-[2rem] border border-white/8 bg-[#090909] p-6">
              <h3 className="text-xl font-medium text-white">{phase.title}</h3>
              <p className="mt-4 text-sm leading-7 text-neutral-400">{phase.text}</p>
            </article>
          ))}
        </div>
      </SectionBlock>

      <SectionBlock
        eyebrow="Operator discipline"
        title="The doctor report should be part of every rollout."
        description="The fastest way to catch broken launchers, wrong working directories, missing env, or dead providers is to check the system from the command the user will actually run."
      >
        <div className="rounded-[2rem] border border-white/8 bg-black/50 p-6">
          <pre className="overflow-x-auto text-sm text-neutral-200">
            <code>{`connect --doctor
connect login
connect dashboard`}</code>
          </pre>
        </div>
      </SectionBlock>
    </div>
  )
}
