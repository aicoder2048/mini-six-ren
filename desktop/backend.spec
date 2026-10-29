# -*- mode: python ; coding: utf-8 -*-
"""只冻结运行所需模块与静态资源，用户配置和源码工作树不进入安装包。"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
nicegui_data, nicegui_binaries, nicegui_hidden = collect_all('nicegui')

analysis = Analysis(
    [str(root / 'src' / 'desktop_server.py')],
    pathex=[str(root / 'src')],
    binaries=nicegui_binaries,
    datas=nicegui_data + copy_metadata('pydantic-ai', recursive=True) + [
        (str(root / 'src' / 'web.css'), '.'),
        (str(root / 'src' / 'themes'), 'themes'),
    ],
    hiddenimports=nicegui_hidden +
        collect_submodules('pydantic_ai.models', on_error='ignore') +
        collect_submodules('pydantic_ai.providers', on_error='ignore'),
    excludes=['tkinter', 'pytest', 'IPython', 'nicegui.native'],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz, analysis.scripts, [], exclude_binaries=True,
    name='mini-six-ren-backend', debug=False, strip=False, upx=False,
    console=True, contents_directory='src',
)
collection = COLLECT(exe, analysis.binaries, analysis.datas,
                     strip=False, upx=False, name='mini-six-ren-backend')
