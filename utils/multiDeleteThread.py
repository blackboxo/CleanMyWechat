import logging
import os
import shutil
import stat

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

    def __init__(self, fileList, dirList, share_thread_arr, direct_delete=False,
                 result_stats=None):
        super(multiDeleteThread, self).__init__()
        self.fileList = fileList
        self.dirList = dirList
        self.share_thread_arr = share_thread_arr
        self.direct_delete = direct_delete
        self.result_stats = result_stats if result_stats is not None else [0, 0]

    def _make_writable(self, file_path):
        original_mode = os.stat(file_path).st_mode
        if not original_mode & stat.S_IWRITE:
            os.chmod(file_path, original_mode | stat.S_IWRITE)
        return original_mode

    def _restore_mode(self, file_path, original_mode):
        if original_mode is None or not os.path.lexists(file_path):
            return
        try:
            os.chmod(file_path, original_mode)
        except OSError:
            logging.exception("Failed to restore file attributes: %s", file_path)

    def _delete_path(self, file_path):
        if is_protected_file(file_path):
            logging.info("Skip protected file: %s", file_path)
            return False
        if not os.path.lexists(file_path):
            logging.info("Path already removed: %s", file_path)
            return True
        original_mode = None
        try:
            # WeChat 4.x marks downloaded files read-only.  Windows rejects
            # os.remove with WinError 5 until the writable bit is restored.
            original_mode = self._make_writable(file_path)
            if self.direct_delete:
                if os.path.isdir(file_path) and not os.path.islink(file_path):
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
            else:
                send2trash(file_path)
            return True
        except Exception:
            logging.exception("Failed to delete path: %s", file_path)
            self._restore_mode(file_path, original_mode)
            return False

    def _emit_progress(self, succeeded):
        qmut.lock()
        try:
            self.share_thread_arr[0] += 1
            self.result_stats[0 if succeeded else 1] += 1
            self.delete_process_signal.emit(self.share_thread_arr[0])
        finally:
            qmut.unlock()

    def run(self):
        try:
            for file_path in self.fileList:
                succeeded = self._delete_path(file_path)
                self._emit_progress(succeeded)

            for file_path in self.dirList:
                succeeded = self._delete_path(file_path)
                self._emit_progress(succeeded)

            logging.info(
                "Delete thread finished: succeeded=%s failed=%s",
                self.result_stats[0], self.result_stats[1])
        finally:
            self.delete_complete_signal.emit()
