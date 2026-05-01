"""
Install the 'imos' command so it works from any terminal.
Run once: python install_imos_command.py
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def install():
    print("Installing IMOS command...")

    if os.name == "nt":
        # Windows: copy imos.bat to a directory on PATH, or add project dir to PATH
        bat_src = PROJECT_ROOT / "imos.bat"

        # Try to add to user PATH via registry
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Environment",
                0,
                winreg.KEY_READ | winreg.KEY_WRITE,
            )
            try:
                current_path, _ = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                current_path = ""

            project_str = str(PROJECT_ROOT)
            if project_str not in current_path:
                new_path = current_path + ";" + project_str if current_path else project_str
                winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
                print(f"  Added {project_str} to user PATH")
                print("  Restart your terminal for PATH changes to take effect.")
            else:
                print(f"  {project_str} already in PATH")
            winreg.CloseKey(key)
        except Exception as e:
            print(f"  Could not modify PATH via registry: {e}")
            print(f"  Manually add to PATH: {PROJECT_ROOT}")

        # Also copy to Python Scripts dir (usually already on PATH)
        scripts_dir = Path(sys.executable).parent / "Scripts"
        if scripts_dir.exists():
            dest = scripts_dir / "imos.bat"
            shutil.copy2(str(bat_src), str(dest))
            print(f"  Copied imos.bat to {dest}")

        print("\nIMOS command installed!")
        print("Open a NEW terminal and type: imos")

    else:
        # Unix: create symlink in /usr/local/bin or ~/.local/bin
        cli_py = PROJECT_ROOT / "imos_cli.py"
        wrapper = f"#!/bin/bash\npython3 {cli_py} \"$@\"\n"

        local_bin = Path.home() / ".local" / "bin"
        local_bin.mkdir(parents=True, exist_ok=True)
        dest = local_bin / "imos"
        dest.write_text(wrapper)
        dest.chmod(0o755)
        print(f"  Created {dest}")
        print("  Make sure ~/.local/bin is in your PATH")
        print("\nIMOS command installed! Type: imos")


if __name__ == "__main__":
    install()
