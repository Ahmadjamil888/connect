import type { ReactNode } from 'react'

type SectionBlockProps = {
  eyebrow: string
  title: string
  description: string
  children: ReactNode
}

export function SectionBlock({ eyebrow, title, description, children }: SectionBlockProps) {
  return (
    <section className="border-t border-white/8 px-5 py-20">
      <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-[#27F3A9]">{eyebrow}</div>
          <h2 className="mt-4 text-4xl font-light tracking-[-0.04em] text-white md:text-5xl">{title}</h2>
          <p className="mt-4 max-w-xl text-base leading-7 text-neutral-400">{description}</p>
        </div>
        <div>{children}</div>
      </div>
    </section>
  )
}
