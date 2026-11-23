# PyInstaller (onedir، بدون کنسول). ساخت: pyinstaller goldsignal.spec --noconfirm
from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("keyring.backends") + ["win32ctypes.pywin32.pywintypes", "win32ctypes.pywin32.win32cred"]
a = Analysis(
    ["run.py"],
    pathex=["src"],
    datas=[("assets", "assets")],
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "scipy", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.Qt3DCore"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="GoldSignal", console=False, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name="GoldSignal")
