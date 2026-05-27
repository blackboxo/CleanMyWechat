import logging
import os

from PyQt5.QtCore import QMutex, QThread, pyqtSignal
from send2trash import send2trash


PROTECTED_EXTS = {
    '.db', '.sqlite', '.sqlite3', '.db-shm', '.db-wal', '.ldb', '.sst',
    '.dll', '.exe', '.msi', '.sys', '.ocx', '.pyd', '.so', '.dylib',
    '.bat', '.cmd', '.ps1', '.vbs', '.js', '.jar', '.pak'
}


def is_protected_file(file_path):
    return os.path.splitext(str(file_path))[1].lower() in PROTECTED_EXTS


qmut = QMutex()


class multiDeleteThread(QThread):
    delete_process_signal = pyqtSignal(int)
    delete_complete_signal = pyqtSignal()

    def __init__(self, fileList, dirList, share_thread_arr):
        super(multiDeleteThread, self).__init__()
        self.fileList = fileList
        self.dirList = dirList
        self.share_thread_arr = share_thread_arr

    def _send_to_trash(self, file_path):
        if is_protected_file(file_path):
            logging.info("Skip protected file: %s", file_path)
            return
        try:
            send2trash(file_path)
        except Exception:
            logging.exception("Failed to move to recycle bin: %s", file_path)

    def _emit_progress(self):
        qmut.lock()
        try:
            self.share_thread_arr[0] += 1
            self.delete_process_signal.emit(self.share_thread_arr[0])
        finally:
            qmut.unlock()

    def run(self):
        try:
            for file_path in self.fileList:
                self._send_to_trash(file_path)
                self._emit_progress()

            for file_path in self.dirList:
                self._send_to_trash(file_path)
                self._emit_progress()

            logging.info("Delete thread finished")
        finally:
            self.delete_complete_signal.emit()
