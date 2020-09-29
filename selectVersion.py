
import getpass
import json
import os

working_dir = os.path.split(os.path.realpath(__file__))[0]

def check_dir(file_path):
    list_ = os.listdir(file_path)
    if 'All Users' in list_ or 'Applet' in list_:
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

class selectVersion:

    def getAllPath(self):
        user = getpass.getuser()
        dic = {
        'pc': 'C:\\Users\\' + user + '\\Documents\\WeChat Files',
        'forwin10': 'C:\\Users\\' + user + '\\AppData\\Local\\Packages\\TencentWeChatLimited.forWindows10_sdtnhv12zgd7a\\LocalCache\\Roaming\\Tencent\\WeChatAppStore\\WeChatAppStore Files',
        'foruwp': 'C:\\Users\\' + user + '\\AppData\\Local\\Packages\\TencentWeChatLimited.WeChatUWP_sdtnhv12zgd7a\\LocalCache\\Roaming\\Tencent\\WeChatAppStore\\WeChatAppStore Files'
        }
        dirlist = []
        for key in dic:
            if os.path.exists(dic[key]):
                list_ = os.listdir(dic[key])
                # 换用lambda 表达式更安全，remove函数如果不存在对象会抛出异常
                list_ = [element for element in list_ if element != 'All Users' and element != 'Applet']
                for i in range(0, len(list_)):
                    file_path = os.path.join(dic[key], list_[i])
                    if os.path.isdir(file_path):
                        dirlist.append(file_path)
                return (dirlist,list_)
            else:
                return ([],[])