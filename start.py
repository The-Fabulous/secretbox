"""Build the website when needed, then run one FastAPI server."""

import argparse
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "secretbox-ui"


def build_needed():
    index = FRONTEND / "dist" / "index.html"
    if not index.is_file():
        return True
    inputs = [FRONTEND / name for name in (
        "index.html", "package.json", "package-lock.json", "vite.config.js",
        ".env", ".env.local", ".env.production", ".env.production.local",
    )]
    for directory in ("src", "public"):
        inputs.extend((FRONTEND / directory).rglob("*"))
    inputs.extend((ROOT / "objects").glob("*_menu.json"))
    return any(path.is_file() and path.stat().st_mtime > index.stat().st_mtime for path in inputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--build", action="store_true", help="Force a website rebuild")
    args = parser.parse_args()
    if args.build or build_needed():
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm:
            print("Install Node.js to build the website, then run this command again.", file=sys.stderr)
            return 1
        try:
            if not (FRONTEND / "node_modules").is_dir():
                subprocess.run([npm, "ci"], cwd=FRONTEND, check=True)
            build_env = os.environ.copy()
            build_env["VITE_API_URL"] = ""
            subprocess.run([npm, "run", "build"], cwd=FRONTEND, env=build_env, check=True)
        except subprocess.CalledProcessError as exc:
            return exc.returncode
    os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(48))
    import uvicorn
    print(f"Website: http://{args.host}:{args.port}/secretbox/", flush=True)
    print(f"API:     http://{args.host}:{args.port}/docs", flush=True)
    uvicorn.run("main:app", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
