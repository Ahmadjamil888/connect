import type { ReactNode } from 'react'

type SectionBlockProps = {
  eyebrow: string
  title: string
  description: string
  children: ReactNode
}

export function SectionBlock({ eyebrow, title, description, children }: SectionBlockProps) {
  return (
    <section className="border-t border-[#1d1a14] px-4 py-20 sm:px-5">
      <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[0.82fr_1.18fr]">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-[#27F3A9]">{eyebrow}</div>
          <h2 className="mt-4 max-w-lg text-3xl font-light tracking-[-0.05em] text-white md:text-5xl">{title}</h2>
          <p className="mt-4 max-w-lg text-[15px] leading-7 text-neutral-400">{description}</p>
        </div>
        <div>{children}</div>
      </div>
    </section>
  )
}
