# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('images', 'images')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Clean My WeChat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file='entitlements.plist',
    icon=['images/icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Clean My WeChat',
)
app = BUNDLE(
    coll,
    name='Clean My WeChat.app',
    icon='images/icon.icns',
    bundle_identifier='com.blackboxo.cleanmywechat',
    info_plist={
        'LSMinimumSystemVersion': '10.15',
        'CFBundleShortVersionString': '3.1.0',
        'NSDesktopFolderUsageDescription': 'Clean My WeChat 需要访问桌面文件夹以扫描微信缓存文件。',
        'NSDocumentsFolderUsageDescription': 'Clean My WeChat 需要访问文稿文件夹以扫描微信缓存文件。',
        'NSDownloadsFolderUsageDescription': 'Clean My WeChat 需要访问下载文件夹以扫描微信缓存文件。',
    },
)
