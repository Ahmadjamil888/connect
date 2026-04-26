import { SectionBlock } from '../components/SectionBlock'

const blocks = [
  ['Gateway', 'Routes sessions, messaging, node state, memory, and workflows through one control plane.'],
  ['Runtime', 'Invokes models, executes tools, persists state, and manages delivery back into channels.'],
  ['Security', 'Supports deployment-aware auth, webhook bearer validation, and protected operator surfaces.'],
  ['Frontend', 'Acts as the public entrypoint for product narrative, sign-in, and operator dashboard handoff.'],
]

const deepDives = [
  {
    title: 'Session continuity',
    text: 'Every connector and dashboard action should land in a session with preserved history, memory context, and visible delivery state. That is what makes the operator usable over time.',
  },
  {
    title: 'Tool governance',
    text: 'Tool profiles, allowlists, deny rules, and typed catalog metadata exist so the runtime can reason safely about what it is permitted to execute in a given context.',
  },
  {
    title: 'Deployment flexibility',
    text: 'The same product can run as a local operator console, a browser-led dashboard flow, or a cloud-exposed gateway with stricter auth and webhook controls.',
  },
]

export function PlatformPage() {
  return (
    <div className="bg-black pt-8">
      <SectionBlock
        eyebrow="Architecture"
        title="One operator system, multiple surfaces"
        description="The product is split deliberately: frontend for narrative and sign-in, backend for execution and control, and a gateway/runtime core that owns state."
      >
        <div className="grid gap-4 md:grid-cols-2">
          {blocks.map(([title, text]) => (
            <div key={title} className="rounded-[2rem] border border-white/8 bg-white/[0.03] p-6">
              <h3 className="text-xl font-medium text-white">{title}</h3>
              <p className="mt-3 text-sm leading-7 text-neutral-400">{text}</p>
            </div>
          ))}
        </div>
      </SectionBlock>

      <SectionBlock
        eyebrow="Runtime model"
        title="Structured enough to govern, dynamic enough to think."
        description="CONNECT is not meant to be a fixed workflow runner disguised as an assistant. The goal is a runtime that can reason dynamically while still remaining observable and operable."
      >
        <div className="grid gap-4">
          {deepDives.map((item) => (
            <article key={item.title} className="rounded-[2rem] border border-white/8 bg-[#090909] p-6">
              <h3 className="text-2xl font-medium text-white">{item.title}</h3>
              <p className="mt-4 text-sm leading-7 text-neutral-400">{item.text}</p>
            </article>
          ))}
        </div>
      </SectionBlock>

      <SectionBlock
        eyebrow="Experience"
        title="The frontend and operator surfaces are separate on purpose."
        description="A public product site should explain, convert, and authenticate. An operator surface should expose live state, execution, and control. CONNECT now treats those as different jobs."
      >
        <div className="rounded-[2rem] border border-white/8 bg-[linear-gradient(180deg,rgba(39,243,169,0.07),rgba(255,255,255,0.02))] p-8">
          <div className="grid gap-4 md:grid-cols-2">
            {[
              ['Public frontend', 'Long-form product narrative, sign-in, navigation, docs, and launch framing.'],
              ['Operator backend', 'Dashboard, workflows, node pairing, messaging, gateway status, and live runtime control.'],
            ].map(([title, text]) => (
              <div key={title} className="rounded-[1.5rem] border border-white/8 bg-black/25 p-5">
                <h3 className="text-xl text-white">{title}</h3>
                <p className="mt-3 text-sm leading-7 text-neutral-400">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </SectionBlock>
    </div>
  )
}
