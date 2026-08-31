import datetime
import os
from PyQt5.QtCore import QThread, pyqtSignal, QMutex

from utils.cleanup_rules import (
    PROTECTED_DIR_NAMES,
    build_account_scan_dirs,
    is_path_expired,
    is_protected_path,
    retention_cutoff,
)


class ScanThread(QThread):
    scan_progress_signal = pyqtSignal(int)
    scan_file_found_signal = pyqtSignal(str, str, str)
    scan_finished_signal = pyqtSignal(int, int)
    scan_error_signal = pyqtSignal(str)

    def __init__(self, config):
        super(ScanThread, self).__init__()
        self.config = config
        self.is_running = True
        self.qmut = QMutex()

    def stop(self):
        self.is_running = False

    def get_file_size_str(self, size):
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.2f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.2f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def get_file_size(self, path):
        try:
            if os.path.isfile(path):
                return os.path.getsize(path)
            elif os.path.isdir(path):
                total_size = 0
                for dirpath, dirnames, filenames in os.walk(path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        try:
                            total_size += os.path.getsize(fp)
                        except:
                            pass
                return total_size
        except:
            pass
        return 0

    def get_fileNum(self, path, day, picCacheCheck, fileCheck, picCheck,
                    videoCheck, file_list, dir_list, user_config=None):
        if not self.is_running:
            return
        user_config = user_config or {}
        include_msg_attach = user_config.get('clean_msg_attach', True)
        seen = set(file_list)
        for scan_path, category in build_account_scan_dirs(
                path, picCacheCheck, fileCheck, picCheck, videoCheck,
                include_msg_attach=include_msg_attach):
            self.pathFileDeal(
                day, scan_path, file_list, dir_list, seen=seen,
                user_config=user_config, category=category)

    def pathFileDeal(self, day, path, file_list, dir_list, seen=None,
                     user_config=None, category='file'):
        if not self.is_running:
            return
        if not os.path.isdir(path):
            return
        seen = seen if seen is not None else set(file_list)
        user_config = user_config or {}
        whitelist_exts = {
            str(ext).lower() if str(ext).startswith('.') else '.' + str(ext).lower()
            for ext in user_config.get('whitelist_exts', [])
            if ext
        }
        whitelist_paths = [
            os.path.normcase(os.path.abspath(os.path.expandvars(str(item))))
            for item in user_config.get('whitelist_paths', [])
            if item
        ]
        cutoff = retention_cutoff(datetime.datetime.now(), day)
        try:
            for root, dirs, files in os.walk(path):
                if not self.is_running:
                    return
                dirs[:] = [d for d in dirs if d.lower() not in PROTECTED_DIR_NAMES]
                root_key = os.path.normcase(os.path.abspath(root))
                if user_config.get('use_whitelist', True) and any(
                        root_key == item or root_key.startswith(item + os.sep)
                        for item in whitelist_paths):
                    dirs[:] = []
                    continue
                for filename in files:
                    if not self.is_running:
                        return
                    file_path = os.path.join(root, filename)
                    ext = os.path.splitext(filename)[1].lower()
                    file_key = os.path.normcase(os.path.abspath(file_path))
                    if file_path in seen or is_protected_path(file_path):
                        continue
                    if user_config.get('use_whitelist', True):
                        if ext in whitelist_exts:
                            continue
                        if any(file_key == item or file_key.startswith(item + os.sep)
                               for item in whitelist_paths):
                            continue
                    if not is_path_expired(file_path, cutoff):
                        continue
                    seen.add(file_path)
                    file_list.append(file_path)
                    file_size = self.get_file_size(file_path)
                    self.scan_file_found_signal.emit(
                        file_path, self.get_file_size_str(file_size), "file")
        except OSError as exc:
            self.scan_error_signal.emit(f"扫描目录失败 {path}: {exc}")

    def getPathFileNum(self, now, day, path_one, path_two, file_list, dir_list):
        # 兼容旧调用；现在统一递归并按单个文件的时间判断。
        seen = set(file_list)
        self.pathFileDeal(day, path_one, file_list, dir_list, seen=seen)
        self.pathFileDeal(day, path_two, file_list, dir_list, seen=seen)

    def run(self):
        try:
            file_list = []
            dir_list = []
            
            i = 0
            users = self.config.get("users", [])
            total_users = len(users)
            if total_users == 0:
                self.scan_finished_signal.emit(0, 0)
                return
            
            for value in users:
                if not self.is_running:
                    break
                
                if value["is_clean"]:
                    account_path = value.get("data_dir")
                    if not account_path and i < len(self.config.get("data_dir", [])):
                        account_path = self.config["data_dir"][i]
                    self.get_fileNum(
                        account_path,
                        int(value.get("clean_days", 365)),
                        value.get("clean_pic_cache", True),
                        value.get("clean_file", False),
                        value.get("clean_pic", True),
                        value.get("clean_video", True),
                        file_list, 
                        dir_list,
                        user_config=value,
                    )
                
                progress = int((i + 1) / total_users * 100)
                self.scan_progress_signal.emit(progress)
                i = i + 1
            
            if self.is_running:
                self.scan_finished_signal.emit(len(file_list), len(dir_list))
            
        except Exception as e:
            self.scan_error_signal.emit(str(e))
