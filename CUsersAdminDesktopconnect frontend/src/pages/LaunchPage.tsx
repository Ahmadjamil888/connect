import { SectionBlock } from '../components/SectionBlock'

const checklist = [
  'Install the runtime and open the shell with `imos`.',
  'Sign in through Clerk in the frontend or by using `imos login` in the CLI.',
  'Use `imos shell --beast` when the goal should fan out across multiple adapters.',
  'Validate sessions, adapters, and dashboard reachability from the same CLI surface the operator will actually use.',
]

const phases = [
  {
    title: 'Installation',
    text: 'Install the repo, verify the global launcher path, and confirm `imos status` and `imos adapters list` report the right runtime state from any working directory.',
  },
  {
    title: 'Authentication',
    text: 'Ensure Clerk env is present on the frontend and backend, then use the browser-to-localhost handoff flow to establish the local session.',
  },
  {
    title: 'Runtime validation',
    text: 'Confirm provider readiness, dashboard availability, session creation, beast-mode routing, and at least one working connector path before broad rollout.',
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
            <code>{`imos
imos status
imos adapters list
imos shell --beast
imos dashboard`}</code>
          </pre>
        </div>
      </SectionBlock>
    </div>
  )
}
