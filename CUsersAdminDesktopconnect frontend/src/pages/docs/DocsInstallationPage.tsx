import { CodeBlock } from '../../components/CodeBlock'
import { DocsShell } from '../../components/DocsShell'

const macLinuxInstall = 'bash -c "$(curl -fsSL https://raw.githubusercontent.com/Ahmadjamil888/connect/main/install.sh)"'
const windowsInstall =
  'cmd /c "curl -L -o connect.zip https://github.com/Ahmadjamil888/connect/archive/refs/heads/main.zip && powershell -Command \\"Expand-Archive -Force connect.zip .\\" && cd connect-main && install.bat"'
const gitBashInstall = 'git clone https://github.com/Ahmadjamil888/connect && cd connect && bash install.sh'

export function DocsInstallationPage() {
  return (
    <DocsShell
      title="Install CONNECT on the machine the operator will actually use."
      description="These commands install the repo and configure the global launcher. The launch path matters because the CLI, dashboard, and auth bridge depend on a stable entrypoint."
    >
      <div className="space-y-6 text-sm leading-8 text-neutral-400">
        <p>Use the installation path that matches your machine and shell.</p>
        <CodeBlock label="Mac and Linux" code={macLinuxInstall} />
        <CodeBlock label="Windows" code={windowsInstall} />
        <CodeBlock label="Windows with Git Bash" code={gitBashInstall} />
        <p>
          After installation, the launcher should be available as <code>connect</code>. If the command resolves to an
          old path, rerun the installer from the current repo so the global launcher in your user PATH is refreshed.
        </p>
        <CodeBlock label="Validate the launcher" code={'connect --doctor'} />
      </div>
    </DocsShell>
  )
}
