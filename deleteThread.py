import os, datetime, time, re
import shutil

from PyQt5.QtCore import QBasicTimer
from dateutil import relativedelta
from send2trash import send2trash
from pathlib import Path, PureWindowsPath


from PyQt5.QtCore import QThread, pyqtSignal

##################################################################
#删除线程
##################################################################
class deleteThread(QThread):
    delete_proess_signal = pyqtSignal(int)                        #创建信号

    def __init__(self, fileNum, path, month, picCacheCheck, fileCheck, picCheck, videoCheck, uwp):
        super(deleteThread, self).__init__()
        self.fileNum = fileNum
        self.path = path
        self.month = month
        self.picCacheCheck = picCacheCheck
        self.fileCheck = fileCheck
        self.picCheck = picCheck
        self.videoCheck = videoCheck
        self.tempNum = 0
        self.uwp = uwp


    def run(self):
        try:
            dirname = PureWindowsPath(self.path)
            # Convert path to the right format for the current operating system
            correct_path = Path(dirname)
            now = datetime.datetime.now()
            if self.picCacheCheck:
                path_one = correct_path / 'Attachment'
                path_two = correct_path / 'FileStorage/Cache'
                self.deleteFile(now, self.month, path_one, path_two)
            if self.fileCheck:
                path_one = correct_path / 'Files'
                path_two = correct_path / 'FileStorage/File'
                self.deleteFile(now, self.month, path_one, path_two)
            if self.picCheck:
                path_one = correct_path / 'Image/Image'
                path_two = correct_path / 'FileStorage/Image'
                self.deleteFile(now, self.month, path_one, path_two)
            if self.videoCheck:
                path_one = correct_path / 'Video'
                path_two = correct_path / 'FileStorage/Video'
                self.deleteFile(now, self.month, path_one, path_two)

            self.exit(0)            #关闭线程
        except Exception as e:
            print(e)

    def deleteFile(self, now, month, path_one, path_two):
        # delete path_one
        if os.path.exists(path_one):
            list = os.listdir(path_one)
            filelist = []
            for i in range(0, len(list)):
                file_path = os.path.join(path_one, list[i])
                if os.path.isfile(file_path):
                    filelist.append(list[i])
            for i in range(0, len(filelist)):
                file_path = os.path.join(path_one, filelist[i])
                if os.path.isdir(file_path):
                    continue
                timestamp = datetime.datetime.fromtimestamp(
                    os.path.getmtime(file_path))
                r = relativedelta.relativedelta(now, timestamp)
                if r.years * 12 + r.months > month:
                    send2trash(file_path)
                    self.tempNum = self.tempNum + 1
                    proess = self.tempNum / int(self.fileNum) * 100
                    self.delete_proess_signal.emit(int(proess))
                    # print("delete:", file_path)

            # delete path_two
        if os.path.exists(path_two) and self.uwp == False:
            osdir = os.listdir(path_two)
            dirlist = []
            for i in range(0, len(osdir)):
                file_path = os.path.join(path_two, osdir[i])
                if os.path.isdir(file_path):
                    dirlist.append(osdir[i])
            for i in range(0, len(dirlist)):
                file_path = os.path.join(path_two, dirlist[i])
                if os.path.isfile(file_path):
                    continue
                if re.match('\d{4}(\-)\d{2}', dirlist[i]) != None:
                    cyear = int(dirlist[i].split('-', 1)[0])
                    cmonth = int(dirlist[i].split('-', 1)[1])
                    diff = (now.year - cyear) * 12 + now.month - cmonth
                    if diff > month:
                        send2trash(file_path)
                        self.tempNum = self.tempNum + 1
                        proess = self.tempNum / int(self.fileNum) * 100
                        self.delete_proess_signal.emit(int(proess))
