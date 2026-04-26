import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

export function DocsAuthenticationPage() {
  return (
    <DocsShell
      title="Authentication is shared between the deployed frontend and the local runtime."
      description="CONNECT uses Clerk on the frontend and validates the session token on the backend before establishing a local operator session."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          The frontend reads <code>NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code>. The backend reads both{' '}
          <code>NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code> and <code>CLERK_SECRET_KEY</code>.
        </p>
        <p>
          CLI login works through the Vercel frontend. When the user runs <code>connect login</code>, the CLI opens the
          web sign-in page, waits on a localhost callback, and stores the verified local session only after the backend
          validates the Clerk token.
        </p>
        <CodeBlock label="Start sign-in from the terminal" code={'connect login'} />
        <p>
          If cloud mode or auth enforcement is enabled, the dashboard and protected APIs require that authenticated local
          session or an accepted bearer token for approved webhook paths.
        </p>
      </div>
    </DocsShell>
  )
}
