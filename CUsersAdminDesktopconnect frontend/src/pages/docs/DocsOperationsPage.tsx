import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

export function DocsOperationsPage() {
  return (
    <DocsShell
      title="Operational confidence starts with the exact command the user will run."
      description="The launcher path, provider health, auth env, connector credentials, and dashboard reachability should all be verified from the real CLI entrypoint."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          Common operator commands include <code>connect</code>, <code>connect dashboard</code>,{' '}
          <code>connect gateway</code>, <code>connect login</code>, and the messaging validation commands in the CLI.
        </p>
        <p>
          For launch builds, verify the launcher path, provider health, Clerk env variables, connector credentials, and
          dashboard reachability. The doctor report is the fastest way to inspect the state of those pieces from any
          directory on the machine.
        </p>
        <CodeBlock
          label="Recommended checks"
          code={`connect --doctor
connect login
connect dashboard`}
        />
      </div>
    </DocsShell>
  )
}
