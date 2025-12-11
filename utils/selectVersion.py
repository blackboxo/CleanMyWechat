
import getpass
import json
import os
import winreg

working_dir = os.path.split(os.path.realpath(__file__))[0]

def check_dir(file_path):
    list_ = os.listdir(file_path)
    if 'All Users' in list_ or 'Applet' in list_ or 'WMPF' in list_:
        return 0
    else:
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
    list_ = os.listdir(filepath)
    # 换用lambda 表达式更安全，remove函数如果不存在对象会抛出异常
    list_ = [element for element in list_ if element != 'All Users' and element != 'Applet' and element != 'WMPF']
    for i in range(0, len(list_)):
        file_path = os.path.join(filepath, list_[i])
        if os.path.isdir(file_path):
            dirlist.append(file_path)
            names.append(list_[i])
    return (dirlist, names)

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
            
        # 注册表路径和字段名
        registry_key_path = r"software\tencent\wechat"
        value_name = "FileSavePath"

        # 读取字段值
        value = read_registry_value(registry_key_path, value_name)

        if value and value != 'MyDocument:' and os.path.isdir(value):
            fpath = os.path.join(value, 'WeChat Files')
            print(fpath)
            return get_dir_name(fpath)
        else:
            return ([], [])

