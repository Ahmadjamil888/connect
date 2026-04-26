import { SignInButton, useAuth } from '@clerk/react'
import HeroSection from '../components/HeroSection'
import { SectionBlock } from '../components/SectionBlock'

type HomePageProps = {
  dashboardUrl: string
}

const logoStrip = ['stripe', 'OpenAI', 'Linear', 'Datadog', 'NVIDIA', 'Figma', 'ramp', 'Adobe']

const showcaseRows = [
  {
    eyebrow: 'Agent Runtime',
    title: 'Agents turn ideas into execution while the operator keeps context.',
    body: 'Sessions, memory, typed tools, and dynamic model reasoning stay in one runtime so the system decides and acts without losing the thread.',
    align: 'left' as const,
    accent: 'Learn about runtime orchestration',
  },
  {
    eyebrow: 'Parallel Work',
    title: 'Autonomous loops run in parallel and return results you can trust.',
    body: 'Background jobs, workflows, and cross-channel messaging make the system useful even when the terminal is closed.',
    align: 'right' as const,
    accent: 'Learn about orchestration',
  },
  {
    eyebrow: 'Tooling',
    title: 'Every tool surface stays visible, typed, and accountable.',
    body: 'Canvas, files, runtime commands, webhooks, and connectors work as one operator fabric instead of a stack of disconnected scripts.',
    align: 'left' as const,
    accent: 'Learn about the tool catalog',
  },
]

const testimonials = [
  {
    quote:
      'The system finally looks and behaves like a product instead of a loose CLI pile. The operator handoff from browser to runtime is clean.',
    author: 'Operator Team',
    role: 'Internal launch review',
  },
  {
    quote:
      'What matters is not just tool count. It is whether sessions, memory, workflows, and connectors stay coherent under load. CONNECT is moving toward that shape.',
    author: 'Platform Review',
    role: 'Architecture pass',
  },
  {
    quote:
      'The new frontend gives the backend a real public face without compromising the local-first runtime model.',
    author: 'Deployment Review',
    role: 'Release preparation',
  },
]

const featureTiles = [
  {
    title: 'Choose the best model for every task',
    text: 'Route between providers, local models, and execution surfaces while preserving one operator experience.',
  },
  {
    title: 'Complete codebase understanding',
    text: 'Move from repo context to tool execution and back again without dropping session memory.',
  },
  {
    title: 'Deploy enduring software',
    text: 'Run the local stack, expose the gateway in cloud mode, and keep auth and webhook controls in place.',
  },
]

function PreviewPanel({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className="rounded-[2rem] border border-[#26231c] bg-[#12100d] p-3 sm:p-4">
      <div className="rounded-[1.6rem] border border-white/6 bg-[#0b0a08] p-4 sm:p-5">
        <div className="flex items-center justify-between border-b border-white/6 pb-3">
          <div className="text-sm text-neutral-400">{title}</div>
          <div className="flex gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
            <span className="h-2.5 w-2.5 rounded-full bg-white/10" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#27F3A9]/70" />
          </div>
        </div>
        <div className="mt-4 grid gap-3">
          {lines.map((line) => (
            <div key={line} className="rounded-2xl border border-white/6 bg-white/[0.03] px-4 py-3 text-sm leading-6 text-neutral-300">
              {line}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ShowcaseBand({
  eyebrow,
  title,
  body,
  align,
  accent,
}: {
  eyebrow: string
  title: string
  body: string
  align: 'left' | 'right'
  accent: string
}) {
  const text = (
    <div className="order-2 flex flex-col justify-center lg:order-none">
      <div className="text-xs uppercase tracking-[0.22em] text-[#27F3A9]">{eyebrow}</div>
      <h3 className="mt-4 max-w-md text-[1.8rem] font-light tracking-[-0.045em] text-white sm:text-4xl">{title}</h3>
      <p className="mt-4 max-w-md text-sm leading-7 text-neutral-400 sm:text-[15px]">{body}</p>
      <div className="mt-5 text-sm text-[#f0a640]">{accent} {'->'}</div>
    </div>
  )

  const preview = (
    <div className="order-1 lg:order-none">
      <PreviewPanel
        title={eyebrow}
        lines={[
          'Gateway dispatch and session routing',
          'Tool invocations with stateful outputs',
          'Memory-backed execution summaries',
          'Operator-visible delivery into chat surfaces',
        ]}
      />
    </div>
  )

  return (
    <section className="border-t border-[#1d1a14] px-4 py-14 sm:px-5 md:py-18">
      <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-2 lg:items-center">
        {align === 'left' ? text : preview}
        {align === 'left' ? preview : text}
      </div>
    </section>
  )
}

export function HomePage({ dashboardUrl }: HomePageProps) {
  const { isSignedIn } = useAuth()

  return (
    <div className="bg-black">
      <HeroSection />

      <section className="border-t border-[#1d1a14] px-4 py-8 sm:px-5">
        <div className="mx-auto max-w-7xl">
          <div className="mb-5 text-center text-[11px] uppercase tracking-[0.24em] text-neutral-500">
            Trusted workflow patterns from teams building production software
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-8">
            {logoStrip.map((name) => (
              <div
                key={name}
                className="flex min-h-14 items-center justify-center rounded-2xl border border-[#201d18] bg-[#100f0d] px-3 text-center text-sm text-neutral-300"
              >
                {name}
              </div>
            ))}
          </div>
        </div>
      </section>

      {showcaseRows.map((row) => (
        <ShowcaseBand key={row.title} {...row} />
      ))}

      <SectionBlock
        eyebrow="Operator Flow"
        title="The public site, sign-in, and runtime handoff now share one path."
        description="The browser layer carries the product narrative, Clerk handles identity, and the operator dashboard takes over only when the user is ready to do real work."
      >
        <div className="rounded-[2rem] border border-[#201d18] bg-[#0c0b09] p-5 sm:p-8">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-[1.5rem] border border-[#201d18] bg-[#12110f] p-5">
              <div className="text-xs uppercase tracking-[0.2em] text-neutral-500">Frontend</div>
              <div className="mt-3 text-lg text-white">Vercel-hosted sign-in and landing experience</div>
              <p className="mt-3 text-sm leading-7 text-neutral-400">
                Users sign in once through Clerk and move cleanly into the operator runtime without having to re-enter credentials in the terminal.
              </p>
            </div>
            <div className="rounded-[1.5rem] border border-[#201d18] bg-[#12110f] p-5">
              <div className="text-xs uppercase tracking-[0.2em] text-neutral-500">Backend</div>
              <div className="mt-3 text-lg text-white">Authenticated dashboard and local control plane</div>
              <p className="mt-3 text-sm leading-7 text-neutral-400">
                The backend validates the Clerk token, stores a local session, and unlocks the dashboard, workflows, nodes, tools, and live operator state.
              </p>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            <a
              href={dashboardUrl}
              target="_blank"
              rel="noreferrer"
              className="rounded-full bg-[#27F3A9] px-5 py-3 text-sm font-medium text-black transition hover:brightness-110"
            >
              Open Operator Dashboard
            </a>
            {!isSignedIn ? (
              <SignInButton mode="modal">
                <button className="rounded-full border border-white/10 px-5 py-3 text-sm text-white transition hover:border-[#27F3A9]/50">
                  Sign in first
                </button>
              </SignInButton>
            ) : (
              <div className="rounded-full border border-[#27F3A9]/25 px-5 py-3 text-sm text-[#9af6d0]">
                Signed in. Operator handoff is ready.
              </div>
            )}
          </div>
        </div>
      </SectionBlock>

      <section className="border-t border-[#1d1a14] px-4 py-20 sm:px-5">
        <div className="mx-auto max-w-7xl">
          <h2 className="text-center text-4xl font-light tracking-[-0.04em] text-white md:text-5xl">
            The new way to operate software.
          </h2>
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {testimonials.map((item) => (
              <article key={item.quote} className="rounded-[2rem] border border-[#201d18] bg-[#0f0e0c] p-6">
                <p className="text-sm leading-7 text-neutral-300">"{item.quote}"</p>
                <div className="mt-8 text-sm text-white">{item.author}</div>
                <div className="text-sm text-neutral-500">{item.role}</div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-[#1d1a14] px-4 py-20 sm:px-5">
        <div className="mx-auto max-w-7xl">
          <div className="text-xs uppercase tracking-[0.22em] text-neutral-500">Stay on the frontier</div>
          <div className="mt-6 grid gap-4 lg:grid-cols-3">
            {featureTiles.map((tile, index) => (
              <article key={tile.title} className="rounded-[2rem] border border-[#201d18] bg-[#0c0b09] p-6">
                <div className="mb-6 h-48 rounded-[1.5rem] border border-[#24211b] bg-[#15120e] p-4">
                  <div className="grid h-full gap-3">
                    <div className="rounded-2xl border border-white/5 bg-black/30" />
                    <div className={`${index === 2 ? 'grid grid-cols-2 gap-3' : 'grid grid-cols-3 gap-3'}`}>
                      <div className="rounded-2xl border border-white/5 bg-black/30" />
                      <div className="rounded-2xl border border-white/5 bg-black/30" />
                      {index !== 2 ? <div className="rounded-2xl border border-white/5 bg-black/30" /> : null}
                    </div>
                  </div>
                </div>
                <h3 className="text-xl font-medium text-white">{tile.title}</h3>
                <p className="mt-3 text-sm leading-7 text-neutral-400">{tile.text}</p>
                <div className="mt-5 text-sm text-[#f0a640]">Explore more {'->'}</div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-[#1d1a14] px-4 py-16 sm:px-5">
        <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[0.72fr_1.28fr]">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-neutral-500">Changelog</div>
            <h2 className="mt-4 text-3xl font-light tracking-[-0.04em] text-white">Live product momentum.</h2>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {[
              ['Apr 26, 2026', 'Clerk-backed CLI handoff to the Vercel frontend'],
              ['Apr 26, 2026', 'Dashboard, gateway, sessions, and workflow control plane'],
              ['Apr 26, 2026', 'Messaging connectors and node/canvas runtime surface'],
            ].map(([date, text]) => (
              <div key={text} className="rounded-[1.6rem] border border-[#201d18] bg-[#0f0e0c] p-5">
                <div className="text-xs uppercase tracking-[0.16em] text-neutral-500">{date}</div>
                <div className="mt-4 text-sm leading-7 text-neutral-300">{text}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
