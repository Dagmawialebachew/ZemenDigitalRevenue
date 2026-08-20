from __future__ import annotations

import argparse
import compileall
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, cwd: Path = ROOT) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic release checks.")
    parser.add_argument("--frontends", action="store_true", help="Also run npm install/build for both React apps.")
    args = parser.parse_args()

    ok = compileall.compile_dir(ROOT / "backend", quiet=1)
    ok &= compileall.compile_dir(ROOT / "bot", quiet=1)
    ok &= compileall.compile_dir(ROOT / "database", quiet=1)
    ok &= compileall.compile_dir(ROOT / "shared", quiet=1)
    ok &= compileall.compile_dir(ROOT / "workers", quiet=1)
    ok &= compileall.compile_dir(ROOT / "scripts", quiet=1)
    if not ok:
        raise SystemExit("Python compile failed")
    env = dict(__import__('os').environ)
    env['PYTHONPATH'] = str(ROOT)
    print("+ pytest -q")
    subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, env=env, check=True)
    requirements = (ROOT / "requirements.txt").read_text().lower()
    if "redis" in requirements:
        raise SystemExit("Redis dependency detected — Zemen v1 architecture forbids it")
    if args.frontends:
        for app, base in (("miniapp", "/store/"), ("dashboard", "/control/")):
            cwd = ROOT / app
            run(["npm", "install", "--no-audit", "--no-fund"], cwd=cwd)
            env2 = dict(__import__('os').environ)
            env2['VITE_BASE_PATH'] = base
            if app == 'miniapp': env2['VITE_API_BASE_URL'] = '/api/miniapp'
            else: env2['VITE_API_BASE'] = ''
            print(f"+ npm run build ({app})")
            subprocess.run(["npm", "run", "build"], cwd=cwd, env=env2, check=True)
    print("Release checks passed.")


if __name__ == "__main__":
    main()
