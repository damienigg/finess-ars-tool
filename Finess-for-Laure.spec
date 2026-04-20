# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec pour Finess-for-Laure (Windows).

Build :
    pyinstaller --clean --noconfirm Finess-for-Laure.spec
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

app_name = "Finess-for-Laure"

# Fichiers data à embarquer tels quels dans le bundle.
datas = [
    ("app/templates", "app/templates"),
    ("app/static", "app/static"),
    ("migrations", "migrations"),
    ("alembic.ini", "."),
]
datas += collect_data_files("pyproj")

# Uvicorn et SQLAlchemy ont des imports dynamiques invisibles pour PyInstaller.
hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("sqlalchemy.dialects.sqlite")
hiddenimports += collect_submodules("app.routers")
hiddenimports += collect_submodules("app.services")
hiddenimports += [
    "anyio._backends._asyncio",
    "email.mime.multipart",
    "email.mime.text",
    "httpx._transports.default",
    "Levenshtein",
]

block_cipher = None

a = Analysis(
    ["app/desktop.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Modules volumineux non utilisés par l'app.
        "tkinter",
        "matplotlib",
        "numpy.testing",
        "pytest",
        "jupyter",
        "IPython",
    ],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # pas de fenêtre console noire
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # à remplir si on ajoute un .ico
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=app_name,
)
