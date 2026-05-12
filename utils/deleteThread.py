import os, datetime, time, re
import shutil
import logging

from send2trash import send2trash

from PyQt5.QtCore import QThread, pyqtSignal, QMutex


PROTECTED_EXTS = {
    '.db', '.sqlite', '.sqlite3', '.db-shm', '.db-wal', '.ldb', '.sst',
    '.dll', '.exe', '.msi', '.sys', '.ocx', '.pyd', '.so', '.dylib',
    '.bat', '.cmd', '.ps1', '.vbs', '.js', '.jar', '.pak'
}


def is_protected_file(file_path):
    return os.path.splitext(str(file_path))[1].lower() in PROTECTED_EXTS


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
                if is_protected_file(file_path):
                    logging.info("跳过受保护文件：%s", file_path)
                    self.tempNum = self.tempNum + 1
                    proess = self.tempNum / int(self.fileNum) * 100 if self.fileNum else 100
                    self.delete_proess_signal.emit(int(proess))
                    continue
                try:
                    send2trash(file_path)
                except Exception:
                    # 记录失败文件，方便用户排查是否被微信占用。
                    logging.exception("移动到回收站失败：%s", file_path)
                self.tempNum = self.tempNum + 1
                proess = self.tempNum / int(self.fileNum) * 100 if self.fileNum else 100
                self.delete_proess_signal.emit(int(proess))

            for file_path in self.dirList:
                try:
                    send2trash(file_path)
                except Exception:
                    logging.exception("移动到回收站失败：%s", file_path)
                self.tempNum = self.tempNum + 1
                proess = self.tempNum / int(self.fileNum) * 100 if self.fileNum else 100
                self.delete_proess_signal.emit(int(proess))

            qmut.unlock()
        except Exception as e:
            logging.exception("删除线程异常")
            qmut.unlock()
