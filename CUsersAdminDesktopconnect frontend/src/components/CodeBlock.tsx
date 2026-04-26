import { useState } from 'react'

type CodeBlockProps = {
  label: string
  code: string
}

export function CodeBlock({ label, code }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="rounded-[1.6rem] border border-white/8 bg-black/50 p-5">
      <div className="flex items-center justify-between gap-4">
        <div className="text-xs uppercase tracking-[0.18em] text-neutral-500">{label}</div>
        <button
          type="button"
          onClick={handleCopy}
          className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-neutral-300 transition hover:border-[#27F3A9]/40 hover:text-white"
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="mt-4 overflow-x-auto text-sm text-neutral-200">
        <code>{code}</code>
      </pre>
    </div>
  )
}
