from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from send2trash import send2trash
import os
import logging

PROTECTED_EXTS = {
    '.db', '.sqlite', '.sqlite3', '.db-shm', '.db-wal', '.ldb', '.sst',
    '.dll', '.exe', '.msi', '.sys', '.ocx', '.pyd', '.so', '.dylib',
    '.bat', '.cmd', '.ps1', '.vbs', '.js', '.jar', '.pak'
}


def is_protected_file(file_path):
    return os.path.splitext(str(file_path))[1].lower() in PROTECTED_EXTS


##################################################################
# 删除线程，支持多进程
##################################################################
qmut = QMutex()


class multiDeleteThread(QThread):
    delete_process_signal = pyqtSignal(int)  # 创建信号

    def __init__(self, fileList, dirList, share_thread_arr):
        super(multiDeleteThread, self).__init__()
        self.fileList = fileList
        self.dirList = dirList
        self.share_thread_arr = share_thread_arr

    def _send_to_trash(self, file_path):
        if is_protected_file(file_path):
            logging.info("跳过受保护文件：%s", file_path)
            return
        try:
            send2trash(file_path)
        except Exception as e:
            # 单个文件失败不影响后续清理，失败原因写入日志。
            logging.exception("移动到回收站失败：%s", file_path)

    def _emit_progress(self):
        qmut.lock()
        self.share_thread_arr[0] += 1
        self.delete_process_signal.emit(self.share_thread_arr[0])
        qmut.unlock()

    def run(self):
        for file_path in self.fileList:
            self._send_to_trash(file_path)
            self._emit_progress()

        for file_path in self.dirList:
            self._send_to_trash(file_path)
            self._emit_progress()

        logging.info('一个清理线程执行结束')
