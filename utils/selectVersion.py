
import getpass
import json
import os
import winreg

working_dir = os.path.split(os.path.realpath(__file__))[0]

def check_dir(file_path):
    if not os.path.exists(file_path):
        return 1
    try:
        list_ = os.listdir(file_path)
        if 'All Users' in list_ or 'Applet' in list_ or 'WMPF' in list_:
            return 0
        else:
            return 1
    except:
        return 1


def existing_user_config():
    if os.path.exists(working_dir + "/config.json"):
        fd = open(working_dir+"/config.json", encoding="utf-8")
        config = json.load(fd)
        user_config = config['users']
        result = {}
        for uc in user_config:
            wechat_id = uc['wechat_id']
            result[wechat_id] = uc
        return result
    else:
        return {}

def read_registry_value(key_path, value_name):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
        value, _ = winreg.QueryValueEx(key, value_name)
        winreg.CloseKey(key)
        return value
    except FileNotFoundError:
        print("Registry key not found.")
    except PermissionError:
        print("Permission denied.")
    except Exception as e:
        print("Error occurred:", str(e))

def get_dir_name(filepath):
    dirlist = []
    names = []
    if not os.path.exists(filepath):
        return ([], [])
    try:
        list_ = os.listdir(filepath)
        list_ = [element for element in list_ if element != 'All Users' and element != 'Applet' and element != 'WMPF']
        for i in range(0, len(list_)):
            file_path = os.path.join(filepath, list_[i])
            if os.path.isdir(file_path):
                dirlist.append(file_path)
                names.append(list_[i])
        return (dirlist, names)
    except:
        return ([], [])

def find_all_wechat_paths():
    """
    智能扫描所有可能的微信数据目录位置
    返回所有找到的有效路径列表
    """
    user = getpass.getuser()
    found_paths = []
    
    common_paths = [
        f'C:\\Users\\{user}\\Documents\\WeChat Files',
        f'C:\\Users\\{user}\\OneDrive\\Documents\\WeChat Files',
        f'D:\\Documents\\WeChat Files',
        f'E:\\Documents\\WeChat Files',
        f'F:\\Documents\\WeChat Files',
        f'C:\\Users\\{user}\\AppData\\Local\\Packages\\TencentWeChatLimited.forWindows10_sdtnhv12zgd7a\\LocalCache\\Roaming\\Tencent\\WeChatAppStore\\WeChatAppStore Files',
        f'C:\\Users\\{user}\\AppData\\Local\\Packages\\TencentWeChatLimited.WeChatUWP_sdtnhv12zgd7a\\LocalCache\\Roaming\\Tencent\\WeChatAppStore\\WeChatAppStore Files',
    ]
    
    for drive in ['C', 'D', 'E', 'F', 'G']:
        common_paths.append(f'{drive}:\\WeChat Files')
        common_paths.append(f'{drive}:\\WeChat\\WeChat Files')
        common_paths.append(f'{drive}:\\Program Files\\Tencent\\WeChat\\WeChat Files')
        common_paths.append(f'{drive}:\\Program Files (x86)\\Tencent\\WeChat\\WeChat Files')
        common_paths.append(f'{drive}:\\Users\\{user}\\WeChat Files')
        common_paths.append(f'{drive}:\\Users\\{user}\\Tencent Files\\WeChat Files')
    
    for path in common_paths:
        if check_dir(path) == 0:
            if path not in found_paths:
                found_paths.append(path)
    
    registry_key_paths = [
        r"software\tencent\wechat",
        r"Software\Tencent\WeChat",
        r"SOFTWARE\Tencent\WeChat",
    ]
    
    for key_path in registry_key_paths:
        value_names = ["FileSavePath", "InstallPath"]
        for value_name in value_names:
            value = read_registry_value(key_path, value_name)
            if value:
                if value == 'MyDocument:':
                    doc_path = f'C:\\Users\\{user}\\Documents\\WeChat Files'
                    if check_dir(doc_path) == 0 and doc_path not in found_paths:
                        found_paths.append(doc_path)
                elif os.path.isdir(value):
                    wechat_path = os.path.join(value, 'WeChat Files')
                    if check_dir(wechat_path) == 0 and wechat_path not in found_paths:
                        found_paths.append(wechat_path)
                    if check_dir(value) == 0 and value not in found_paths:
                        found_paths.append(value)
    
    try:
        for key_path in registry_key_paths:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        if 'WeChat' in subkey_name or 'Wechat' in subkey_name or 'wechat' in subkey_name:
                            subkey_path = f"{key_path}\\{subkey_name}"
                            value = read_registry_value(subkey_path, "FileSavePath")
                            if value and os.path.isdir(value):
                                wechat_path = os.path.join(value, 'WeChat Files')
                                if check_dir(wechat_path) == 0 and wechat_path not in found_paths:
                                    found_paths.append(wechat_path)
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except:
                pass
    except:
        pass
    
    return found_paths

class selectVersion:

    def getAllPath(self):
        user = getpass.getuser()
        dic = {
        'pc': 'C:\\Users\\' + user + '\\Documents\\WeChat Files',
        'forwin10': 'C:\\Users\\' + user + '\\AppData\\Local\\Packages\\TencentWeChatLimited.forWindows10_sdtnhv12zgd7a\\LocalCache\\Roaming\\Tencent\\WeChatAppStore\\WeChatAppStore Files',
        'foruwp': 'C:\\Users\\' + user + '\\AppData\\Local\\Packages\\TencentWeChatLimited.WeChatUWP_sdtnhv12zgd7a\\LocalCache\\Roaming\\Tencent\\WeChatAppStore\\WeChatAppStore Files'
        }
        for key in dic:
            if os.path.exists(dic[key]):
                return get_dir_name(dic[key])
            
        registry_key_path = r"software\tencent\wechat"
        value_name = "FileSavePath"

        value = read_registry_value(registry_key_path, value_name)

        if value and value != 'MyDocument:' and os.path.isdir(value):
            fpath = os.path.join(value, 'WeChat Files')
            print(fpath)
            return get_dir_name(fpath)
        else:
            return ([], [])
