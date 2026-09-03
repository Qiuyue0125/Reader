import os
from PyInstaller.utils.hooks import collect_submodules

project_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(project_dir, 'main.py')],
    pathex=[project_dir],
    binaries=[],
    datas=[(os.path.join(project_dir, 'logo.png'), '.')],
    hiddenimports=collect_submodules('mobi'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'cv2',
              'PyQt5', 'PyQt6', 'PySide2', 'IPython', 'jupyter'],
    noarchive=False,
    optimize=0,
)

a.binaries = [
    item for item in a.binaries
    if '\\.cache\\codex-runtimes\\' not in item[1].lower()
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='reader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_dir, 'logo.png'),
)
