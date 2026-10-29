#!/usr/bin/env python3
"""在当前平台构建内置 Python 后端，保留原有 src/../data 相对布局。"""

from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'dist' / 'desktop-backend'


def main():
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--distpath', str(OUTPUT), '--workpath', str(ROOT / 'build' / 'desktop-backend'),
        str(ROOT / 'desktop' / 'backend.spec'),
    ], cwd=ROOT, check=True)
    destination = OUTPUT / 'mini-six-ren-backend'
    shutil.copytree(ROOT / 'data', destination / 'data', dirs_exist_ok=True)
    forbidden = [path for path in destination.rglob('*') if path.name in {'.env', '.env.sample'}]
    if forbidden:
        raise RuntimeError('构建中发现不应分发的配置文件，请检查打包规则。')
    print(f'桌面后端构建完成：{destination}')


if __name__ == '__main__':
    main()
