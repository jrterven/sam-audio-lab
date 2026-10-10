"""Launch SAM Audio Lab on loopback; use the sam3 conda environment."""
import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--build', action='store_true', help='Rebuild the web UI before starting')
    args = parser.parse_args()
    if os.name == 'nt':
        parser.error('En Windows ejecuta la aplicación dentro de WSL2. Consulta docs/INSTALLATION.md.')
    if args.build or not (ROOT/'web/dist/index.html').exists():
        subprocess.run(['npm', 'run', 'build'], cwd=ROOT/'web', check=True)
    os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
    os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '60')
    import uvicorn
    print(f'SAM Audio Lab → http://127.0.0.1:{args.port}', flush=True)
    uvicorn.run('lab.api:app', host='127.0.0.1', port=args.port, access_log=False, timeout_graceful_shutdown=3)


if __name__ == '__main__':
    main()
