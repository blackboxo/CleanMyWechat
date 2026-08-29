import logging

from PyQt5.QtCore import QMutex, QThread, pyqtSignal
from send2trash import send2trash

from utils.cleanupManifest import cleanup_result_summary, delete_path_for_manifest


qmut = QMutex()


class multiDeleteThread(QThread):
    delete_process_signal = pyqtSignal(int)
    delete_complete_signal = pyqtSignal(dict)

    def __init__(self, fileList, dirList, share_thread_arr, direct_delete=False, trash_func=None, delete_func=None):
        super(multiDeleteThread, self).__init__()
        self.fileList = fileList
        self.dirList = dirList
        self.share_thread_arr = share_thread_arr
        self.direct_delete = direct_delete
        self.trash_func = trash_func or send2trash
        self.delete_func = delete_func
        self.records = []
        self.result = cleanup_result_summary([], direct_delete=direct_delete)

    def _delete_path(self, file_path, item_type):
        record = delete_path_for_manifest(
            file_path,
            item_type,
            direct_delete=self.direct_delete,
            trash_func=self.trash_func,
            delete_func=self.delete_func,
        )
        if record["status"] == "skipped":
            logging.info("Skip cleanup path: %s (%s)", file_path, record.get("reason", ""))
        elif record["status"] == "failed":
            logging.error("Failed to delete path: %s: %s", file_path, record.get("error", ""))
        return record

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
                self.records.append(self._delete_path(file_path, "file"))
                self._emit_progress()

            for file_path in self.dirList:
                self.records.append(self._delete_path(file_path, "dir"))
                self._emit_progress()

            logging.info("Delete thread finished")
        finally:
            self.result = cleanup_result_summary(self.records, direct_delete=self.direct_delete)
            self.delete_complete_signal.emit(self.result)
