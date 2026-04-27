import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

const macLinuxInstall = 'curl -fsSL https://raw.githubusercontent.com/Ahmadjamil888/connect/main/install.sh | bash'
const windowsInstall =
  'powershell -ExecutionPolicy Bypass -Command "Invoke-WebRequest https://raw.githubusercontent.com/Ahmadjamil888/connect/main/install.bat -OutFile $env:TEMP\\connect-install.bat; & $env:TEMP\\connect-install.bat"'
const gitBashInstall = 'curl -fsSL https://raw.githubusercontent.com/Ahmadjamil888/connect/main/install.sh | bash'
const repoInstall = 'git clone https://github.com/Ahmadjamil888/connect && cd connect && ./install.sh'

export function DocsInstallationPage() {
  return (
    <DocsShell
      title="Install CONNECT on the machine the operator will actually use."
      description="These commands install the repo and configure the global launcher. The launch path matters because the CLI, dashboard, and auth bridge depend on a stable entrypoint."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>Use the installation path that matches your machine and shell.</p>
        <CodeBlock label="Mac and Linux" code={macLinuxInstall} />
        <CodeBlock label="Windows PowerShell or Command Prompt" code={windowsInstall} />
        <CodeBlock label="Windows with Git Bash" code={gitBashInstall} />
        <CodeBlock label="Install from a local clone" code={repoInstall} />
        <p>
          After installation, the launcher should be available as <code>connect</code>. The installer now sets up the
          virtual environment, refreshes the global launcher, and leaves the shell ready for <code>connect --doctor</code>{' '}
          or <code>connect</code>.
        </p>
        <CodeBlock label="Validate the launcher" code={'connect --doctor'} />
      </div>
    </DocsShell>
  )
}
