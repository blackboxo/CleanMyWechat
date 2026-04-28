import os, datetime, re
from pathlib import Path, PureWindowsPath
from PyQt5.QtCore import QThread, pyqtSignal, QMutex


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

    def get_fileNum(self, path, day, picCacheCheck, fileCheck, picCheck, videoCheck, file_list, dir_list):
        if not self.is_running:
            return
        
        dir_name = PureWindowsPath(path)
        correct_path = Path(dir_name)
        now = datetime.datetime.now()
        
        if picCacheCheck:
            path_one = correct_path / 'Attachment'
            path_two = correct_path / 'FileStorage/Cache'
            self.getPathFileNum(now, day, path_one, path_two, file_list, dir_list)
        
        if fileCheck:
            path_one = correct_path / 'Files'
            path_two = correct_path / 'FileStorage/File'
            self.getPathFileNum(now, day, path_one, path_two, file_list, dir_list)
        
        if picCheck:
            path_one = correct_path / 'Image/Image'
            path_two = correct_path / 'FileStorage/Image'
            self.getPathFileNum(now, day, path_one, path_two, file_list, dir_list)
        
        if videoCheck:
            path_one = correct_path / 'Video'
            path_two = correct_path / 'FileStorage/Video'
            self.getPathFileNum(now, day, path_one, path_two, file_list, dir_list)

    def pathFileDeal(self, now, day, path, file_list, dir_list):
        if not self.is_running:
            return
        
        if os.path.exists(path):
            filelist = [
                f for f in os.listdir(path)
                if os.path.isfile(os.path.join(path, f))
            ]
            for i in range(0, len(filelist)):
                if not self.is_running:
                    return
                
                file_path = os.path.join(path, filelist[i])
                if os.path.isdir(file_path):
                    continue
                
                try:
                    timestamp = datetime.datetime.fromtimestamp(
                        os.path.getmtime(file_path))
                    diff = (now - timestamp).days
                    if diff >= day:
                        file_list.append(file_path)
                        file_size = self.get_file_size(file_path)
                        file_size_str = self.get_file_size_str(file_size)
                        self.scan_file_found_signal.emit(file_path, file_size_str, "file")
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
                    continue

    def getPathFileNum(self, now, day, path_one, path_two, file_list, dir_list):
        if not self.is_running:
            return
        
        self.pathFileDeal(now, day, path_one, file_list, dir_list)
        
        td = datetime.datetime.now() - datetime.timedelta(days=day)
        td_year = td.year
        td_month = td.month
        
        if os.path.exists(path_two):
            osdir = os.listdir(path_two)
            dirlist = []
            for i in range(0, len(osdir)):
                file_path = os.path.join(path_two, osdir[i])
                if os.path.isdir(file_path):
                    dirlist.append(osdir[i])
            
            for i in range(0, len(dirlist)):
                if not self.is_running:
                    return
                
                file_path = os.path.join(path_two, dirlist[i])
                if os.path.isfile(file_path):
                    continue
                
                if re.match('\d{4}(\-)\d{2}', dirlist[i]) != None:
                    cyear = int(dirlist[i].split('-', 1)[0])
                    cmonth = int(dirlist[i].split('-', 1)[1])
                    if self.__before_deadline(cyear, cmonth, td_year, td_month):
                        dir_list.append(file_path)
                        file_size = self.get_file_size(file_path)
                        file_size_str = self.get_file_size_str(file_size)
                        self.scan_file_found_signal.emit(file_path, file_size_str, "dir")
                    else:
                        if cmonth == td_month:
                            self.pathFileDeal(now, day, file_path, file_list, dir_list)

    def __before_deadline(self, cyear, cmonth, td_year, td_month):
        if cyear < td_year:
            return True
        elif cyear > td_year:
            return False
        elif cyear == td_year:
            return cmonth < td_month

    def run(self):
        try:
            file_list = []
            dir_list = []
            
            i = 0
            total_users = len(self.config["users"])
            
            for value in self.config["users"]:
                if not self.is_running:
                    break
                
                if value["is_clean"]:
                    self.get_fileNum(
                        self.config["data_dir"][i],
                        int(value["clean_days"]),
                        value["clean_pic_cache"], 
                        value["clean_file"],
                        value["clean_pic"], 
                        value["clean_video"],
                        file_list, 
                        dir_list
                    )
                
                progress = int((i + 1) / total_users * 100)
                self.scan_progress_signal.emit(progress)
                i = i + 1
            
            if self.is_running:
                self.scan_finished_signal.emit(len(file_list), len(dir_list))
            
        except Exception as e:
            self.scan_error_signal.emit(str(e))
