import winreg

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

# 注册表路径和字段名
registry_key_path = r"software\tencent\wechat"
value_name = "FileSavePath"

# 读取字段值
value = read_registry_value(registry_key_path, value_name)

# 打印字段值
if value:
    print("FileSavePath value:", value)
