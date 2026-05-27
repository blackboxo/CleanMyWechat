import getpass
import json
import os
from pathlib import Path
try:
    import winreg
except ImportError:
    winreg = None

utils_dir = os.path.dirname(os.path.abspath(__file__))
working_dir = os.path.dirname(utils_dir)
CONFIG_PATH = os.path.join(working_dir, "config.json")

IGNORED_ROOT_NAMES = {
    'All Users', 'Applet', 'WMPF', 'Global', 'config', 'Config', 'Common',
    'Update', 'Temp', 'temp', 'log', 'logs'
}


def is_wechat_like_account_dir(file_path):
    """判断一个目录是否像微信/企业微信账号数据目录。"""
    if not file_path or not os.path.isdir(file_path):
        return False
    try:
        names = {name.lower() for name in os.listdir(file_path)}
    except Exception:
        return False

    if 'filestorage' in names or 'msgattach' in names or 'msg' in names:
        return True

    # 企业微信常见目录里会出现 Cache，并按月份继续存文件。
    if 'cache' in names and ('file' in names or 'image' in names or 'video' in names or 'voice' in names):
        return True

    return False


def search_account_dirs(base_path, max_depth=4):
    """在给定目录下寻找微信/企业微信账号目录，兼容 Windows 和企业微信多层路径。"""
    result = []
    seen = set()
    if not base_path or not os.path.isdir(base_path):
        return result

    base_path = os.path.abspath(os.path.expanduser(base_path))
    base_depth = len(Path(base_path).parts)
    try:
        if is_wechat_like_account_dir(base_path):
            result.append(base_path)
            seen.add(os.path.normcase(base_path))
            return result

        for root, dirs, files in os.walk(base_path):
            current_depth = len(Path(root).parts) - base_depth
            if current_depth > max_depth:
                dirs[:] = []
                continue

            dirs[:] = [d for d in dirs if d not in IGNORED_ROOT_NAMES and not d.startswith('.')]
            if is_wechat_like_account_dir(root):
                key = os.path.normcase(root)
                if key not in seen:
                    result.append(root)
                    seen.add(key)
                dirs[:] = []
    except Exception:
        pass
    return result


def check_dir(file_path):
    try:
        if search_account_dirs(file_path):
            return 0
        list_ = os.listdir(file_path)
        if 'All Users' in list_ or 'Applet' in list_ or 'WMPF' in list_:
            return 0
    except Exception:
        return 1
    else:
        return 1


def existing_user_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding='utf-8') as f:
            content = json.load(f)
            data = content.get('users', [])
        dic = {v['wechat_id']: v for v in data}
        return dic
    else:
        return {}


def read_registry_value(key_path, value_name):
    if winreg is None:
        return None
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
        value, _ = winreg.QueryValueEx(key, value_name)
        winreg.CloseKey(key)
        return value
    except FileNotFoundError:
        print("Registry key or value not found.")
    except Exception as e:
        print("Error occurred:", str(e))


def get_dir_name(filepath):
    dirlist = []
    names = []
    if not filepath or not os.path.exists(filepath):
        return (dirlist, names)

    account_dirs = search_account_dirs(filepath)
    for account_dir in account_dirs:
        name = os.path.basename(account_dir.rstrip(os.sep))
        if not name:
            name = account_dir
        if 'wxwork' in account_dir.lower() and not name.lower().startswith('wxwork'):
            name = 'WXWork-' + name
        dirlist.append(account_dir)
        names.append(name)

    if not dirlist:
        try:
            list_ = os.listdir(filepath)
            list_ = [element for element in list_ if element not in IGNORED_ROOT_NAMES]
            for item in list_:
                file_path = os.path.join(filepath, item)
                if os.path.isdir(file_path):
                    dirlist.append(file_path)
                    names.append(item)
        except Exception:
            pass
    return (dirlist, names)


class selectVersion:

    def getAllPath(self):
        user = getpass.getuser()
        candidates = [
            os.path.join(r'C:\Users', user, 'Documents', 'WeChat Files'),
            os.path.join(r'C:\Users', user, 'Documents', 'WXWork'),
            os.path.join(r'C:\Users', 'Public', 'Documents', 'WXWork'),
            os.path.join(r'C:\Users', user, 'AppData', 'Local', 'Packages', 'TencentWeChatLimited.forWindows10_sdtnhv12zgd7a', 'LocalCache', 'Roaming', 'Tencent', 'WeChatAppStore', 'WeChatAppStore Files'),
            os.path.join(r'C:\Users', user, 'AppData', 'Local', 'Packages', 'TencentWeChatLimited.WeChatUWP_sdtnhv12zgd7a', 'LocalCache', 'Roaming', 'Tencent', 'WeChatAppStore', 'WeChatAppStore Files')
        ]
        appdata = os.environ.get('APPDATA')
        if appdata:
            candidates.extend([
                os.path.join(appdata, 'Tencent', 'WeChat', 'WeChat Files'),
                os.path.join(appdata, 'Tencent', 'WXWork'),
            ])
        localappdata = os.environ.get('LOCALAPPDATA')
        if localappdata:
            candidates.extend([
                os.path.join(localappdata, 'Tencent', 'WeChat', 'WeChat Files'),
                os.path.join(localappdata, 'Tencent', 'WXWork'),
            ])

        for path in candidates:
            if os.path.exists(path):
                result = get_dir_name(path)
                if result[0]:
                    return result

        registry_key_path = r"software\tencent\wechat"
        value_name = "FileSavePath"
        value = read_registry_value(registry_key_path, value_name)

        if value and value != 'MyDocument:' and os.path.isdir(value):
            fpath = os.path.join(value, 'WeChat Files')
            return get_dir_name(fpath)
        else:
            return ([], [])
