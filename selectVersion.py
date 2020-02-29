
import getpass
import os


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
                list = os.listdir(dic[key])
                for i in range(0, len(list)):
                    if list[i]=='All Users' or list[i]=='Applet':
                        continue
                    file_path = os.path.join(dic[key], list[i])
                    if os.path.isdir(file_path):
                        dirlist.append(file_path)
        return dirlist