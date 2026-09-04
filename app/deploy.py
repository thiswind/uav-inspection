"""Portable installation and single-process serving (Python standard library only)."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / 'uav-inspection-backend'
FRONTEND = ROOT / 'uav-inspection-ui'
ENVIRONMENT = ROOT / '.venv-deploy'
ENV_PYTHON = ENVIRONMENT / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def data_directory(override: str | None = None) -> Path:
    configured = override or os.environ.get('UAV_DATA_DIR')
    if configured:
        return Path(configured).expanduser().resolve()
    marker = ROOT / 'deployment-layout.json'
    if marker.is_file():
        layout = json.loads(marker.read_text(encoding='utf-8'))
        return (ROOT / layout['data_directory']).resolve()
    return ROOT  # Preserve the original development tree until a delivery is built.


def environment(data_dir: Path) -> dict[str, str]:
    result = os.environ.copy()
    result.update(UAV_DATA_DIR=str(data_dir), PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    result.setdefault('YOLO_CONFIG_DIR', str(data_dir / '.cache' / 'ultralytics'))
    return result


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def npm_command() -> str:
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    node = shutil.which('node')
    if not npm or not node:
        raise RuntimeError('Node.js/npm not found. Install Node.js 22.12+ (or 24 LTS), then reopen the terminal.')
    version = subprocess.check_output([node, '--version'], text=True).strip().lstrip('v')
    major, minor, *_ = [int(part) for part in version.split('.')]
    if not ((major == 20 and minor >= 19) or (major == 22 and minor >= 12) or major >= 24):
        raise RuntimeError(f'Node.js {version} is too old. Use Node.js 22.12+ or 24 LTS.')
    return npm


def require_environment() -> None:
    if not ENV_PYTHON.is_file():
        raise RuntimeError('Deployment environment missing. Run setup.bat (Windows) or bash setup.sh first.')


def install(args: argparse.Namespace) -> None:
    if not (3, 10) <= sys.version_info[:2] < (3, 14):
        raise RuntimeError('Use Python 3.10-3.13; Python 3.12 is recommended for the pinned dependencies.')
    npm = None if args.backend_only else npm_command()
    if not ENV_PYTHON.is_file():
        if ENVIRONMENT.exists():
            raise RuntimeError(f'Incomplete environment at {ENVIRONMENT}; it was not overwritten. Rename it and retry.')
        print(f'Creating isolated deployment environment: {ENVIRONMENT}', flush=True)
        venv.EnvBuilder(with_pip=True).create(ENVIRONMENT)
    env = environment(data_directory(args.data_dir))
    run([str(ENV_PYTHON), '-m', 'pip', 'install', '-r', str(BACKEND / 'requirements.txt')], env=env)
    if args.inference:
        print('Installing optional CPU inference dependencies (large download).', flush=True)
        run([str(ENV_PYTHON), '-m', 'pip', 'install', 'torch==2.9.1', 'torchvision==0.24.1',
             '--index-url', 'https://download.pytorch.org/whl/cpu'], env=env)
        run([str(ENV_PYTHON), '-m', 'pip', 'install', '-r', str(BACKEND / 'requirements-inference.txt')], env=env)
    if npm:
        run([npm, 'ci', '--no-audit', '--no-fund'], cwd=FRONTEND, env=env)
        run([npm, 'run', 'build'], cwd=FRONTEND, env=env)
    print('Installation complete. Run start.bat or bash start.sh. Data is optional.', flush=True)


def start(args: argparse.Namespace) -> None:
    require_environment()
    frontend_dist = Path(os.getenv('UAV_FRONTEND_DIST', str(FRONTEND / 'dist'))).resolve()
    if not args.backend_only and not (frontend_dist / 'index.html').is_file():
        raise RuntimeError('Frontend has not been built. Run setup first, or use start --backend-only for API development.')
    data_dir = data_directory(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    env = environment(data_dir)
    print(f'Data directory: {data_dir}', flush=True)
    print(f'Open http://127.0.0.1:{args.port}  |  API docs: /docs  |  Ctrl+C to stop', flush=True)
    if args.host not in {'127.0.0.1', 'localhost', '::1'}:
        print('WARNING: No authentication is configured. Expose only on a trusted teaching LAN, not the public Internet.', flush=True)
    run([str(ENV_PYTHON), '-m', 'uvicorn', 'heatmapapp.main:app', '--host', args.host,
         '--port', str(args.port)], cwd=BACKEND, env=env)


def dev(args: argparse.Namespace) -> None:
    env = environment(data_directory(args.data_dir))
    env['UAV_BACKEND_URL'] = args.backend_url
    run([npm_command(), 'run', 'dev', '--', '--host', args.host], cwd=FRONTEND, env=env)


def doctor(args: argparse.Namespace) -> None:
    data_dir = data_directory(args.data_dir)
    print(f'Program: {ROOT}\nData: {data_dir}\nData folder exists: {data_dir.exists()} (optional)')
    print(f'Deployment Python: {ENV_PYTHON}\nEnvironment exists: {ENV_PYTHON.is_file()}')
    print(f'Frontend built: {(FRONTEND / "dist" / "index.html").is_file()}')
    if ENV_PYTHON.is_file():
        run([str(ENV_PYTHON), '-m', 'pip', 'check'])
    try:
        print(f'npm: {npm_command()}')
    except RuntimeError as exc:
        print(str(exc))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('install', 'start', 'dev', 'doctor'):
        command = commands.add_parser(name)
        command.add_argument('--data-dir', help='Optional data root; defaults to sibling 02-data in a delivery')
        command.set_defaults(action=globals()[name])
        if name in {'install', 'start'}:
            command.add_argument('--backend-only', action='store_true')
        if name == 'install':
            command.add_argument('--inference', action='store_true', help='Also download optional CPU AI packages')
        if name in {'start', 'dev'}:
            command.add_argument('--host', default='127.0.0.1')
        if name == 'start':
            command.add_argument('--port', type=int, default=8002)
        if name == 'dev':
            command.add_argument('--backend-url', default='http://127.0.0.1:8002')
    args = parser.parse_args(argv)
    try:
        args.action(args)
        return 0
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
