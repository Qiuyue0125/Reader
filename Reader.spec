import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

project_dir = Path(SPEC).resolve().parent
python_dir = Path(sys.base_prefix).resolve()
environment_dir = Path(sys.prefix).resolve()
windows_dir = Path(os.environ.get('WINDIR', 'C:/Windows')).resolve()

# 只收集本项目环境和系统动态库。
os.environ['PATH'] = os.pathsep.join(str(path) for path in (
    environment_dir / 'Scripts', python_dir, python_dir / 'DLLs',
    windows_dir / 'System32', windows_dir,
))

a = Analysis(
    [str(project_dir / 'src/main.py')], pathex=[str(project_dir / 'src')],
    binaries=[],
    datas=[(str(project_dir / 'assets/logo.png'), 'assets'),
           (str(environment_dir / 'Lib/site-packages/PySide6/translations/qtbase_zh_CN.qm'), 'PySide6/translations')],
    hiddenimports=collect_submodules('mobi'), hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'cv2',
              'PyQt5', 'PyQt6', 'PySide2', 'IPython', 'jupyter'],
    noarchive=False, optimize=0,
)
allowed_roots = (project_dir, environment_dir, python_dir, windows_dir)
a.binaries = [item for item in a.binaries
              if any(Path(item[1]).resolve().is_relative_to(root) for root in allowed_roots)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name='reader', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    disable_windowed_traceback=False, icon=str(project_dir / 'assets/logo.png'),
)
