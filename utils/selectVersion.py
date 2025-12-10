
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
    
    # 排除已知的非微信账号目录，包括backup和all_users的各种变体
    exclude_dirs = ['All Users', 'Applet', 'WMPF', 'all users', 'applet', 'wmpf', 'all_users', 'backup', 'wax_fca', 'Backup', 'All_users', 'ALL USERS']
    exclude_dirs_lower = [dir_name.lower() for dir_name in exclude_dirs]
    
    for i in range(0, len(list_)):
        dir_name = list_[i]
        file_path = os.path.join(filepath, dir_name)
        
        # 跳过非目录项
        if not os.path.isdir(file_path):
            continue
        
        # 跳过已知的非微信账号目录
        if dir_name.lower() in exclude_dirs_lower:
            continue
        
        # 检查目录结构，判断是否为微信用户目录
        # 旧版本结构：Msg、FileStorage、config
        # 新版本结构：msg、cache、config
        try:
            # 获取当前目录下的子目录列表（转换为小写）
            subdirs = [subdir.lower() for subdir in os.listdir(file_path)]
            
            # 检查旧版本结构：Msg、FileStorage、config
            is_old_version = all(subdir in subdirs for subdir in ['msg', 'filestorage', 'config'])
            
            # 检查新版本结构：msg、cache、config
            is_new_version = all(subdir in subdirs for subdir in ['msg', 'cache', 'config'])
            
            # 符合其中一种结构就算是微信用户目录
            if is_old_version or is_new_version:
                dirlist.append(file_path)
                names.append(dir_name)
                print(f"识别为微信用户目录：{file_path}")
            else:
                print(f"不是微信用户目录，跳过：{file_path}")
        except Exception as e:
            print(f"检查目录 {file_path} 失败：{str(e)}")
            continue
    
    return (dirlist, names)

class selectVersion:

    def getAllPath(self):
        user = getpass.getuser()
        dic = {
        'pc': 'C:/Users/' + user + '/Documents/WeChat Files',
        'forwin10': 'C:/Users/' + user + '/AppData/Local/Packages/TencentWechatLimited.forWindows10_sdtnhv12zgd7a/LocalCache/Roaming/Tencent/WeChatAppStore/WeChatAppStore Files',
        'foruwp': 'C:/Users/' + user + '/AppData/Local/Packages/TencentWechatLimited.WeChatUWP_sdtnhv12zgd7a/LocalCache/Roaming/Tencent/WeChatAppStore/WeChatAppStore Files',
        'pc_xwechat': 'C:/Users/' + user + '/Documents/xwechat_files',
        'pc_d_wechat': 'd:/WeChat Files',
        'pc_d_xwechat': 'd:/xwechat_files',
        }
        
        all_user_dirs = []
        all_user_names = []
        
        # 检查所有可能的微信目录
        for key in dic:
            if os.path.exists(dic[key]):
                dirs, names = get_dir_name(dic[key])
                all_user_dirs.extend(dirs)
                all_user_names.extend(names)
        
        # 如果没有找到任何目录，检查注册表
        if not all_user_dirs:
            # 注册表路径和字段名
            registry_key_path = r"software	encent\wechat"
            value_name = "FileSavePath"

            # 读取字段值
            value = read_registry_value(registry_key_path, value_name)

            if value and value != 'MyDocument:' and os.path.isdir(value):
                fpath = os.path.join(value, 'WeChat Files')
                if os.path.exists(fpath):
                    return get_dir_name(fpath)
            
            # 检查 XWechat Files 目录（最新版微信可能使用此目录）
            xwechat_path = 'C:/Users/' + user + '/Documents/XWechat Files'
            if os.path.exists(xwechat_path):
                return get_dir_name(xwechat_path)
        
        # 如果找到了目录，返回所有目录
        if all_user_dirs:
            return (all_user_dirs, all_user_names)
        else:
            return ([], [])

