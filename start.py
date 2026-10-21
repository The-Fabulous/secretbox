import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "secretbox-ui"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def stop_processes(processes):
    running = [process for process in processes if process.poll() is None]
    if os.name == "nt":
        for process in running:
            try:
                process.send_signal(signal.CTRL_BREAK_EVENT)
            except OSError:
                process.terminate()
    else:
        for process in running:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    for process in running:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def main():
    if not FRONTEND.is_dir():
        print("Could not find the frontend folder:", FRONTEND, file=sys.stderr)
        return 1
    if not (FRONTEND / "node_modules").is_dir():
        print(
            "Frontend dependencies are missing. Run "
            "`npm.cmd install` from secretbox-ui first.",
            file=sys.stderr,
        )
        return 1

    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        print("npm was not found. Install Node.js, then try again.", file=sys.stderr)
        return 1

    python = str(VENV_PYTHON) if VENV_PYTHON.is_file() else sys.executable
    api_env = os.environ.copy()
    api_env.setdefault("SECRET_KEY", secrets.token_urlsafe(48))

    api_command = [
        python,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--reload",
    ]
    frontend_command = f'"{npm}" run dev -- --host 127.0.0.1'
    process_options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    processes = []

    try:
        processes.append(
            subprocess.Popen(
                api_command,
                cwd=ROOT,
                env=api_env,
                **process_options,
            )
        )
        processes.append(
            subprocess.Popen(
                frontend_command,
                cwd=FRONTEND,
                shell=True,
                **process_options,
            )
        )

        print("SecretBox is starting.")
        print("Website: http://127.0.0.1:5173/secretbox/")
        print("API:     http://127.0.0.1:8000/docs")
        print("Press Ctrl+C to stop both services.")

        while True:
            for process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    return exit_code or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping SecretBox...")
        return 0
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
