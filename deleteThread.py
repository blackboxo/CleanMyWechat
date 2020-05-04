import os, datetime, time, re
import shutil

from send2trash import send2trash

from PyQt5.QtCore import QThread, pyqtSignal, QMutex


##################################################################
#删除线程
##################################################################
qmut = QMutex()
class deleteThread(QThread):
    delete_proess_signal = pyqtSignal(int)  #创建信号

    def __init__(self, fileList, dirList):
        super(deleteThread, self).__init__()
        self.fileList = fileList
        self.dirList = dirList
        self.fileNum = len(fileList) + len(dirList)
        self.tempNum = 0

    def run(self):
        qmut.lock()
        try:
            for file_path in self.fileList:
                send2trash(file_path)
                self.tempNum = self.tempNum + 1
                proess = self.tempNum / int(self.fileNum) * 100
                self.delete_proess_signal.emit(int(proess))

            for file_path in self.dirList:
                send2trash(file_path)
                self.tempNum = self.tempNum + 1
                proess = self.tempNum / int(self.fileNum) * 100
                self.delete_proess_signal.emit(int(proess))

            qmut.unlock()
            self.exec_()  #关闭线程
        except Exception as e:
            print(e)