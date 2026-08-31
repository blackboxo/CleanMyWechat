import datetime
import os
from pathlib import Path


PROTECTED_EXTS = {
    '.db', '.sqlite', '.sqlite3', '.db-shm', '.db-wal', '.ldb', '.sst',
    '.dll', '.exe', '.msi', '.sys', '.ocx', '.pyd', '.so', '.dylib',
    '.bat', '.cmd', '.ps1', '.vbs', '.js', '.jar', '.pak'
}

PROTECTED_DIR_NAMES = {
    'bin', 'runtime', 'runtimes', 'plugin', 'plugins', 'xplugin', 'module', 'modules',
    'framework', 'frameworks', 'locales', 'resources', 'swiftshader', 'installer',
    'update', 'updates', 'crashpad', 'web_shell', 'multitab'
}


def retention_cutoff(now, days):
    """Return the exact time boundary for files that may be cleaned."""
    try:
        normalized_days = max(int(days), 0)
    except (TypeError, ValueError):
        normalized_days = 0
    return now - datetime.timedelta(days=normalized_days)


def is_path_expired(path, cutoff):
    """Use the file-system modification time instead of folder-name guesses."""
    try:
        modified_at = datetime.datetime.fromtimestamp(os.path.getmtime(path))
        return modified_at <= cutoff
    except (OSError, OverflowError, ValueError):
        return False


def is_protected_path(path):
    path_str = str(path)
    if os.path.splitext(path_str)[1].lower() in PROTECTED_EXTS:
        return True
    return any(part.lower() in PROTECTED_DIR_NAMES for part in Path(path_str).parts)


def build_account_scan_dirs(account_path, clean_cache, clean_files, clean_images,
                            clean_videos, include_msg_attach=True):
    """Build the media roots used by both preview and cleanup scans.

    WeChat 4.x stores media below ``msg`` while older releases use the
    ``FileStorage`` layout.  Keep both layouts so upgrading WeChat does not
    silently disable a selected cleanup category.
    """
    if not account_path:
        return []
    account_path = Path(os.path.normpath(str(account_path)))
    scan_dirs = []

    if clean_cache:
        scan_dirs.extend([
            (account_path / 'Attachment', 'cache'),
            (account_path / 'FileStorage' / 'Cache', 'cache'),
        ])
    if clean_files:
        scan_dirs.extend([
            (account_path / 'Files', 'file'),
            (account_path / 'FileStorage' / 'File', 'file'),
        ])
    if clean_images:
        scan_dirs.extend([
            (account_path / 'Image' / 'Image', 'image'),
            (account_path / 'FileStorage' / 'Image', 'image'),
        ])
    if clean_videos:
        scan_dirs.extend([
            (account_path / 'Video', 'video'),
            (account_path / 'FileStorage' / 'Video', 'video'),
        ])

    msg_root = account_path / 'msg'
    is_xwechat_account = (
        'xwechat_files' in str(account_path).lower()
        or any((msg_root / name).is_dir() for name in ('attach', 'file', 'video'))
    )
    if is_xwechat_account:
        if clean_cache:
            scan_dirs.extend([
                (account_path / 'cache', 'cache'),
                (account_path / 'temp', 'cache'),
                (account_path / 'apm_record', 'cache'),
                (account_path / 'business' / 'InputTemp', 'cache'),
                (account_path / 'business' / 'emoticon' / 'Temp', 'cache'),
                (account_path / 'business' / 'emoticon' / 'Thumb', 'cache'),
                (account_path / 'business' / 'xweb', 'cache'),
            ])
        if clean_files:
            scan_dirs.extend([
                (msg_root / 'file', 'file'),
                (account_path / 'business' / 'favorite', 'file'),
            ])
        if clean_images and include_msg_attach:
            scan_dirs.extend([
                (msg_root / 'attach', 'image'),
                (account_path / 'FileStorage' / 'MsgAttach', 'image'),
                (account_path / 'MsgAttach', 'image'),
            ])
        if clean_videos:
            scan_dirs.append((msg_root / 'video', 'video'))

    result = []
    seen = set()
    for path, category in scan_dirs:
        normalized = os.path.abspath(os.path.normpath(str(path)))
        key = (os.path.normcase(normalized), category)
        if key not in seen:
            seen.add(key)
            result.append((normalized, category))
    return result
