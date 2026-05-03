import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

export function DocsOperationsPage() {
  return (
    <DocsShell
      title="Operational confidence starts with the exact IMOS commands the user will run."
      description="Verify launcher health, providers, wake services, adapters, palettes, shell access, and dashboard reachability from the public imos entrypoint."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          Common operator commands now include <code>imos</code>, <code>imos dashboard</code>, <code>imos status</code>,{' '}
          <code>imos adapters list</code>, <code>imos wake status</code>, and the shell-side commands visible through{' '}
          <code>/help</code>.
        </p>
        <p>
          For launch builds, verify provider health, adapter availability, wake-word status, dashboard reachability, and
          the shell command surface. The operator should be able to open IMOS from any directory and drive the system
          without needing internal file names.
        </p>
        <CodeBlock
          label="Recommended checks"
          code={`imos
imos status
imos adapters list
imos sessions list
imos shell --beast
imos wake status
imos palette set --shell ember --dashboard ember
imos dashboard`}
        />
      </div>
    </DocsShell>
  )
}
