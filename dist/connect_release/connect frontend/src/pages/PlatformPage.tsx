import { SectionBlock } from '../components/SectionBlock'

const blocks = [
  ['Gateway', 'Routes sessions, messaging, node state, memory, and workflows through one control plane.'],
  ['Runtime', 'Invokes models, executes tools, persists state, and manages delivery back into channels.'],
  ['Security', 'Supports deployment-aware auth, webhook bearer validation, and protected operator surfaces.'],
  ['Frontend', 'Acts as the public entrypoint for product narrative, sign-in, and operator dashboard handoff.'],
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
              <p className="mt-3 text-sm leading-6 text-neutral-400">{text}</p>
            </div>
          ))}
        </div>
      </SectionBlock>
    </div>
  )
}
