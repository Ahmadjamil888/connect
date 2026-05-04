import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

export function DocsOperationsPage() {
  return (
    <DocsShell
      title="CLI and Commands"
      description="Use the IMOS CLI as the primary operator surface: start the runtime, inspect health, manage sessions, control voice, and open the dashboard without relying on internal implementation details."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          The main public entrypoints are <code>imos</code>, <code>imos --setup</code>, <code>imos --status</code>, and
          the shell-side command surface shown by <code>/help</code> after the runtime starts.
        </p>
        <p>
          Once inside the shell, operators can manage sessions, routing, voice, contacts, dashboard access, and natural
          language actions from the same prompt. That keeps the product behavior consistent between local launch,
          dashboard use, and automation handoff.
        </p>
        <CodeBlock
          label="Recommended launch sequence"
          code={`imos --setup
imos
/help
/doctor
/dashboard
/session list
/listen status
/voice test`}
        />
        <CodeBlock
          label="Core shell commands"
          code={`RUNTIME
imos
imos --setup
imos --shell
imos --server
imos --status

SESSIONS
/session new <name>
/session list
/session resume <name>
/session save
/session export <name>

SYSTEM
/dashboard
/dashboard stop
/doctor
/autostart enable
/autostart disable
/consent`}
        />
        <CodeBlock
          label="Natural-language examples"
          code={`open chrome
message ali send the updated build
email sara about the launch checklist
create folder client-proposals
screenshot
restart
build a landing page
find clients in fintech`}
        />
      </div>
    </DocsShell>
  )
}
