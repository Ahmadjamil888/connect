const principles = [
  {
    title: 'One control plane',
    text: 'CONNECT is built around a gateway and runtime instead of a pile of disconnected automations. Sessions, tools, memory, and messaging live in one operator loop.',
  },
  {
    title: 'Public surface, private execution',
    text: 'The frontend is a clean public entrypoint. The dashboard and runtime stay authenticated and operational behind that surface.',
  },
  {
    title: 'Dynamic before static',
    text: 'The product should think, route, and adapt based on current context. Typed tools matter, but they exist to support the runtime rather than replace it.',
  },
]

const timeline = [
  ['Foundation', 'The local-first runtime, gateway status model, sessions, memory, and typed tool catalog were established as the backbone.'],
  ['Operator UX', 'The CLI, dashboard, and browser handoff were tightened so the product behaves like one system instead of separate utilities.'],
  ['Launch Layer', 'The Vercel frontend, Clerk-auth bridge, docs surface, and production-style site structure now frame the runtime like an actual product.'],
]

export function AboutPage() {
  return (
    <div className="bg-black pt-8">
      <section className="border-b border-white/8 px-5 py-20">
        <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[0.95fr_1.05fr]">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-[#27F3A9]">About CONNECT</div>
            <h1 className="mt-4 text-4xl font-light tracking-[-0.05em] text-white md:text-6xl">
              Built to operate AI systems like real software, not demos.
            </h1>
          </div>
          <div className="space-y-5 text-base leading-8 text-neutral-400">
            <p>
              CONNECT exists to turn AI from an isolated chat surface into an operator-grade system. It combines gateway
              routing, authenticated access, sessions, memory, tools, workflows, and messaging into one runtime that can
              reason and execute with continuity.
            </p>
            <p>
              The product is intentionally split into layers. The public frontend explains the product and handles sign-in.
              The dashboard exposes live state and control. The runtime owns actual execution. That separation keeps the
              experience clean without hiding operational truth.
            </p>
          </div>
        </div>
      </section>

      <section className="border-b border-white/8 px-5 py-20">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-4 md:grid-cols-3">
            {principles.map((item) => (
              <article key={item.title} className="rounded-[2rem] border border-white/8 bg-white/[0.03] p-6">
                <h2 className="text-2xl font-medium text-white">{item.title}</h2>
                <p className="mt-4 text-sm leading-7 text-neutral-400">{item.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="border-b border-white/8 px-5 py-20">
        <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[0.7fr_1.3fr]">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-neutral-500">Why it matters</div>
            <h2 className="mt-4 text-3xl font-light tracking-[-0.04em] text-white md:text-5xl">
              AI systems fail when execution, context, and identity do not stay aligned.
            </h2>
          </div>
          <div className="grid gap-4">
            {[
              'A chat model by itself does not provide deployment, sessions, memory, workflows, or channel delivery.',
              'A tool stack by itself does not provide coherent reasoning or operator-visible state.',
              'A public frontend by itself does not make the runtime safer, more controllable, or more launchable.',
              'CONNECT treats those as one product problem instead of separate implementation chores.',
            ].map((text) => (
              <div key={text} className="rounded-[1.6rem] border border-white/8 bg-[#090909] p-5 text-sm leading-7 text-neutral-300">
                {text}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-5 py-20">
        <div className="mx-auto max-w-7xl">
          <div className="text-xs uppercase tracking-[0.22em] text-neutral-500">Path</div>
          <div className="mt-8 grid gap-4 lg:grid-cols-3">
            {timeline.map(([title, text], index) => (
              <article key={title} className="rounded-[2rem] border border-white/8 bg-white/[0.03] p-6">
                <div className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[#27F3A9]/25 text-sm text-[#27F3A9]">
                  0{index + 1}
                </div>
                <h3 className="mt-5 text-xl font-medium text-white">{title}</h3>
                <p className="mt-3 text-sm leading-7 text-neutral-400">{text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
