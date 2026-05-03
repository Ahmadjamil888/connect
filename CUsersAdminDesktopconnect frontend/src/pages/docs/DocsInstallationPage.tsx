import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

const macLinuxInstall = 'git clone https://github.com/Ahmadjamil888/connect && cd connect && ./install.sh'
const windowsInstall = 'git clone https://github.com/Ahmadjamil888/connect && cd connect && .\\install.cmd'
const gitBashInstall = 'git clone https://github.com/Ahmadjamil888/connect && cd connect && ./install.sh'
const remoteInstallRoutes = `Windows installer route
https://github.com/Ahmadjamil888/connect/install.cmd

macOS and Linux installer route
https://github.com/Ahmadjamil888/connect/install.sh`
const setupFlow = `imos
imos status
imos adapters list
imos shell --beast
imos dashboard
imos sessions list`

export function DocsInstallationPage() {
  return (
    <DocsShell
      title="Install IMOS on the machine the operator will actually use."
      description="Use the public installer route, let it build the runtime with the guided loader, and launch everything through the imos command."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>Use the installation path that matches your machine and shell. The installer shows a guided loader, installs dependencies, prepares the launcher, and runs staged checks automatically.</p>
        <CodeBlock label="Installer routes" code={remoteInstallRoutes} />
        <CodeBlock label="Mac and Linux" code={macLinuxInstall} />
        <CodeBlock label="Windows PowerShell or Command Prompt" code={windowsInstall} />
        <CodeBlock label="Windows with Git Bash" code={gitBashInstall} />
        <p>
          After installation, the launcher should be available as <code>imos</code>. The installer sets up the virtual
          environment, installs the global launcher, initializes local IMOS config, installs MCP and wake services, and
          leaves the machine ready to launch the shell, beast mode, sessions, or dashboard directly.
        </p>
        <CodeBlock label="First-run commands" code={setupFlow} />
      </div>
    </DocsShell>
  )
}
