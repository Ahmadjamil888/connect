import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

const macLinuxInstall = 'git clone https://github.com/Ahmadjamil888/connect && cd connect && ./install.sh'
const windowsInstall = 'git clone https://github.com/Ahmadjamil888/connect && cd connect && .\\install.cmd'
const gitBashInstall = 'git clone https://github.com/Ahmadjamil888/connect && cd connect && ./install.sh'
const remoteInstallRoutes = `Windows installer route
https://github.com/Ahmadjamil888/connect/install.cmd

macOS and Linux installer route
https://github.com/Ahmadjamil888/connect/install.sh`
const setupFlow = `imos --setup
imos
imos --status
/help
/doctor
/dashboard`

export function DocsInstallationPage() {
  return (
    <DocsShell
      title="Getting Started"
      description="Install IMOS on the operator machine, run the setup wizard once, and launch the runtime through the public imos command."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>
          Use the installation path that matches your machine and shell. The installer prepares dependencies, installs
          the launcher, configures the local runtime, and leaves the machine ready to start from the single public
          command surface.
        </p>
        <CodeBlock label="Installer routes" code={remoteInstallRoutes} />
        <CodeBlock label="Mac and Linux" code={macLinuxInstall} />
        <CodeBlock label="Windows PowerShell or Command Prompt" code={windowsInstall} />
        <CodeBlock label="Windows with Git Bash" code={gitBashInstall} />
        <p>
          After installation, launch the first-run wizard with <code>imos --setup</code> or simply run{' '}
          <code>imos</code> and let the runtime guide the remaining setup. The wizard handles provider selection, voice,
          wake word, integrations, consent, and autostart preferences.
        </p>
        <CodeBlock label="First-run commands" code={setupFlow} />
        <p>
          Once the runtime is up, the shell prompt becomes the main operator surface. Use <code>/help</code> to see the
          full command map, <code>/doctor</code> for a health report, and <code>/dashboard</code> to open the local
          control plane in the browser.
        </p>
      </div>
    </DocsShell>
  )
}
