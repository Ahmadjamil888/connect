import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

export function DocsAuthenticationPage() {
  return (
    <DocsShell
      title="Sign-In and Access"
      description="Authentication is shared between the deployed frontend and the local runtime so the CLI and dashboard can inherit a verified operator session."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          The frontend reads <code>NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code>. The backend reads both{' '}
          <code>NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code> and <code>CLERK_SECRET_KEY</code>.
        </p>
        <p>
          CLI login works through the frontend. When the user runs <code>/login</code> from the shell, IMOS opens the
          sign-in page, waits on a localhost callback, and stores the verified local session only after the backend
          validates the token.
        </p>
        <CodeBlock label="Open the authenticated runtime" code={`imos
/login
imos dashboard`} />
        <p>
          The dashboard can also participate in the same signed-in operator flow. If cloud mode or auth enforcement is
          enabled, protected APIs expect that verified local session or an accepted bearer token for approved webhook
          paths.
        </p>
      </div>
    </DocsShell>
  )
}
