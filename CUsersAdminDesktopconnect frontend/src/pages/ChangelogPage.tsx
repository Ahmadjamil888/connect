const entries = [
  {
    date: 'April 26, 2026',
    title: 'Docs navigation, code copy blocks, and changelog surface',
    text: 'The frontend now has dedicated docs routes, reusable code blocks with copy actions, and a fuller product information surface.',
  },
  {
    date: 'April 26, 2026',
    title: 'Vercel Clerk bridge for CLI login',
    text: 'CLI sign-in now redirects to the deployed Vercel frontend and returns to the local runtime through a localhost callback.',
  },
  {
    date: 'April 26, 2026',
    title: 'Dashboard, gateway, sessions, workflows, and connectors',
    text: 'The operator stack now includes a real dashboard surface, runtime orchestration, messaging connectors, and service-oriented launch paths.',
  },
]

export function ChangelogPage() {
  return (
    <div className="bg-black pt-8">
      <section className="border-b border-white/8 px-5 py-20">
        <div className="mx-auto max-w-7xl">
          <div className="text-xs uppercase tracking-[0.22em] text-[#27F3A9]">Changelog</div>
          <h1 className="mt-4 max-w-4xl text-4xl font-light tracking-[-0.05em] text-white md:text-6xl">
            Product momentum, captured in public.
          </h1>
          <p className="mt-6 max-w-3xl text-base leading-8 text-neutral-400">
            This page tracks visible improvements to the frontend, auth flow, launcher behavior, dashboard surface, and
            runtime-facing product layers.
          </p>
        </div>
      </section>

      <section className="px-5 py-16">
        <div className="mx-auto max-w-7xl space-y-4">
          {entries.map((entry) => (
            <article key={entry.title} className="rounded-[2rem] border border-white/8 bg-white/[0.03] p-6">
              <div className="text-xs uppercase tracking-[0.16em] text-neutral-500">{entry.date}</div>
              <h2 className="mt-4 text-2xl text-white">{entry.title}</h2>
              <p className="mt-4 text-sm leading-7 text-neutral-400">{entry.text}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
