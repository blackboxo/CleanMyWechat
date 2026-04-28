import sys

from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsDropShadowEffect, QListWidgetItem, QListView, QWidget, \
    QLabel, QHBoxLayout, QFileDialog, QTableWidgetItem, QHeaderView
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal, QMutex, QSize, QEvent, QPoint, QTimer
from PyQt5.QtGui import QMouseEvent, QCursor, QColor
from PyQt5.uic import loadUi

from pathlib import Path, PureWindowsPath
from dateutil import relativedelta
import utils.resources
import os, datetime, time, re, math, shutil, json

from utils.deleteThread import *
from utils.multiDeleteThread import multiDeleteThread
from utils.selectVersion import *
from utils.selectVersion import check_dir, existing_user_config
from utils.scanThread import ScanThread

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

if getattr(sys, 'frozen', False):
    working_dir = os.path.dirname(os.path.realpath(sys.executable))
elif __file__:
    working_dir = os.path.split(os.path.realpath(__file__))[0]

class Window(QMainWindow):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.m_drag = True
            self.m_DragPosition = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, QMouseEvent):
        try:
            if Qt.LeftButton and self.m_drag:
                self.move(QMouseEvent.globalPos() - self.m_DragPosition)
                QMouseEvent.accept()
        except:
            pass

    def mouseReleaseEvent(self, QMouseEvent):
        self.m_drag = False

    def _frame(self):
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        effect = QGraphicsDropShadowEffect(blurRadius=12, xOffset=0, yOffset=0)
        effect.setColor(QColor(25, 25, 25, 170))
        self.mainFrame.setGraphicsEffect(effect)

    def doFadeIn(self):
        self.animation = QPropertyAnimation(self, b'windowOpacity')
        self.animation.setDuration(250)
        try:
            self.animation.finished.disconnect(self.close)
        except:
            pass
        self.animation.stop()
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.start()

    def doFadeOut(self):
        self.animation.stop()
        self.animation.finished.connect(self.close)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.start()

    def setWarninginfo(self, text):
        self.lab_info.setStyleSheet("""
            .QLabel {
                border:1px solid #ffccc7;
                border-radius:3px;
                line-height: 140px;
                padding: 5px;
                color: #434343;
                background: #fff2f0;
            }
            """)
        self.lab_info.setWordWrap(True)
        self.lab_info.setText(text)

    def setSuccessinfo(self, text):
        self.lab_info.setStyleSheet("""
            .QLabel {
                border:1px solid #b7eb8f;
                border-radius:3px;
                line-height: 140px;
                padding: 5px;
                color: #434343;
                background: #f6ffed;
            }
            """)
        self.lab_info.setWordWrap(True)
        self.lab_info.setText(text)


class ConfigWindow(Window):
    Signal_OneParameter = pyqtSignal(int)

    config = {}

    def _connect(self):
        self.combo_user.currentIndexChanged.connect(self.refresh_ui)
        self.btn_close.clicked.connect(self.save_config)
        self.btn_file.clicked.connect(self.open_file)

    def open_file(self):
        openfile_path = QFileDialog.getExistingDirectory(self, '选择微信数据目录', '')
        if not openfile_path or openfile_path == '':
            return False
        if check_dir(openfile_path) == 0:
            self.setSuccessinfo('读取路径成功！')
            list_ = os.listdir(openfile_path)
            user_list = [
                elem for elem in list_
                if elem != 'All Users' and elem != 'Applet' and elem != 'WMPF'
            ]
            dir_list = []
            user_config = []
            existing_user_config_dic = existing_user_config()
            for user_wx_id in user_list:
                dir_list.append(os.path.join(openfile_path, user_wx_id))
                if user_wx_id in existing_user_config_dic:
                    user_config.append(existing_user_config_dic[user_wx_id])
                else:
                    user_config.append({
                        "wechat_id": user_wx_id,
                        "clean_days": "365",
                        "is_clean": True,
                        "clean_pic_cache": True,
                        "clean_file": False,
                        "clean_pic": True,
                        "clean_video": True,
                        "is_timer": True,
                        "timer": "0h"
                    })

            config = {"data_dir": dir_list, "users": user_config}

            with open(
                    working_dir + "/config.json", "w", encoding="utf-8") as f:
                json.dump(config, f)
            self.load_config()
        else:
            self.setWarninginfo('请选择正确的文件夹！\n一般是WeChat Files文件夹。')

    def save_config(self):
        self.update_config()
        self.doFadeOut()

    def check_wechat_exists(self):
        self.selectVersion = selectVersion()
        self.scan = self.selectVersion.getAllPath()
        self.version_scan = self.scan[0]
        self.users_scan = self.scan[1]
        if len(self.version_scan) == 0:
            return False
        else:
            return True

    def load_config(self):
        fd = open(working_dir + "/config.json", encoding="utf-8")
        self.config = json.load(fd)

        self.combo_user.clear()
        for value in self.config["users"]:
            self.combo_user.addItem(value["wechat_id"])

        self.line_gobackdays.setText(
            str(self.config["users"][0]["clean_days"]))
        self.check_is_clean.setChecked(self.config["users"][0]["is_clean"])
        self.check_picdown.setChecked(self.config["users"][0]["clean_pic"])
        self.check_files.setChecked(self.config["users"][0]["clean_file"])
        self.check_video.setChecked(self.config["users"][0]["clean_video"])
        self.check_picscache.setChecked(
            self.config["users"][0]["clean_pic_cache"])
        self.setSuccessinfo("请确认每个账号的删除内容及时间，以防误删！")

    def refresh_ui(self):
        self.config = open(working_dir + "/config.json", encoding="utf-8")
        self.config = json.load(self.config)

        for value in self.config["users"]:
            if value["wechat_id"] == self.combo_user.currentText():
                self.line_gobackdays.setText(str(value["clean_days"]))
                self.check_is_clean.setChecked(value["is_clean"])
                self.check_picdown.setChecked(value["clean_pic"])
                self.check_files.setChecked(value["clean_file"])
                self.check_video.setChecked(value["clean_video"])
                self.check_picscache.setChecked(value["clean_pic_cache"])

    def create_config(self):
        if not os.path.exists(working_dir + "/config.json"):
            if not self.check_wechat_exists():
                self.setWarninginfo("默认位置没有微信，请自定义位置")
                return

            self.config = {"data_dir": self.version_scan, "users": []}
            for value in self.users_scan:
                self.config["users"].append({
                    "wechat_id": value,
                    "clean_days": 365,
                    "is_clean": True,
                    "clean_pic_cache": True,
                    "clean_file": False,
                    "clean_pic": True,
                    "clean_video": True,
                    "is_timer": True,
                    "timer": "0h"
                })
            with open(
                    working_dir + "/config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f)
            self.load_config()
            self.setSuccessinfo("请确认每个账号的删除内容及时间，以防误删！")
        else:
            self.setSuccessinfo("请确认每个账号的删除内容及时间，以防误删！")
            self.load_config()

    def update_config(self):
        if not len(self.config):
            return
        else:
            for value in self.config["users"]:
                if value["wechat_id"] == self.combo_user.currentText():
                    try:
                        days = int(self.line_gobackdays.text())
                        if days < 0:
                            value["clean_days"] = "0"
                        else:
                            value["clean_days"] = self.line_gobackdays.text()
                    except ValueError:
                        value["clean_days"] = "0"
                    value["is_clean"] = self.check_is_clean.isChecked()
                    value["clean_pic"] = self.check_picdown.isChecked()
                    value["clean_file"] = self.check_files.isChecked()
                    value["clean_video"] = self.check_video.isChecked()
                    value["clean_pic_cache"] = self.check_picscache.isChecked()

            with open(working_dir + "/config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f)
            self.setSuccessinfo("更新配置文件成功")
            self.Signal_OneParameter.emit(1)

    def __init__(self):
        super().__init__()
        loadUi(working_dir + "/images/config.ui", self)

        self._frame()
        self._connect()

        self.doFadeIn()
        self.create_config()

        self.show()


class MainWindow(Window):

    def deal_emit_slot(self, set_status):
        if set_status and not self.config_exists:
            self.setSuccessinfo("已经准备好，可以开始了！")
            self.config_exists = True

    def closeEvent(self, event):
        if hasattr(self, 'scan_thread') and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.scan_thread.wait()
        sys.exit(0)

    def eventFilter(self, object, event):
        if event.type() == QEvent.MouseButtonPress:
            if object == self.lab_close:
                self.doFadeOut()
                return True
            elif object == self.lab_clean:
                try:
                    self.setSuccessinfo("正在一键清理中...")
                    self.justdoit()
                except:
                    self.setWarninginfo("清理失败，请检查配置文件后重试")
                return True
            elif object == self.lab_config:
                cw = ConfigWindow()
                cw.Signal_OneParameter.connect(self.deal_emit_slot)
                return True
            elif object == self.lab_preview:
                try:
                    self.start_preview()
                except Exception as e:
                    self.setWarninginfo(f"预览失败：{str(e)}")
                return True
            elif object == self.lab_execute_delete:
                try:
                    self.execute_delete()
                except Exception as e:
                    self.setWarninginfo(f"删除失败：{str(e)}")
                return True
        return False

    def _eventfilter(self):
        self.lab_close.installEventFilter(self)
        self.lab_clean.installEventFilter(self)
        self.lab_config.installEventFilter(self)
        self.lab_preview.installEventFilter(self)
        self.lab_execute_delete.installEventFilter(self)

    def init_table(self):
        self.table_files.setColumnCount(3)
        self.table_files.setHorizontalHeaderLabels(["选择", "文件路径", "大小"])
        self.table_files.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table_files.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_files.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table_files.setColumnWidth(0, 50)
        self.table_files.setColumnWidth(2, 100)
        self.table_files.setRowCount(0)
        self.file_data = []

    def clear_table(self):
        self.table_files.setRowCount(0)
        self.file_data = []
        self.check_select_all.setChecked(False)

    def add_file_to_table(self, file_path, file_size, file_type):
        row = self.table_files.rowCount()
        self.table_files.insertRow(row)
        
        checkbox_item = QTableWidgetItem()
        checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        checkbox_item.setCheckState(Qt.Checked)
        self.table_files.setItem(row, 0, checkbox_item)
        
        path_item = QTableWidgetItem(file_path)
        path_item.setToolTip(file_path)
        self.table_files.setItem(row, 1, path_item)
        
        size_item = QTableWidgetItem(file_size)
        self.table_files.setItem(row, 2, size_item)
        
        self.file_data.append({"path": file_path, "type": file_type})

    def start_preview(self):
        if not os.path.exists(working_dir + "/config.json"):
            self.setWarninginfo("请先配置微信数据目录")
            return
        
        if hasattr(self, 'scan_thread') and self.scan_thread.isRunning():
            self.setWarninginfo("正在扫描中，请稍候...")
            return
        
        self.clear_table()
        self.bar_progress.setValue(0)
        self.setSuccessinfo("正在扫描文件，请稍候...")
        
        fd = open(working_dir + "/config.json", encoding="utf-8")
        config = json.load(fd)
        
        self.scan_thread = ScanThread(config)
        self.scan_thread.scan_progress_signal.connect(self.on_scan_progress)
        self.scan_thread.scan_file_found_signal.connect(self.on_scan_file_found)
        self.scan_thread.scan_finished_signal.connect(self.on_scan_finished)
        self.scan_thread.scan_error_signal.connect(self.on_scan_error)
        self.scan_thread.start()

    def on_scan_progress(self, progress):
        self.bar_progress.setValue(progress)

    def on_scan_file_found(self, file_path, file_size, file_type):
        self.add_file_to_table(file_path, file_size, file_type)

    def on_scan_finished(self, file_count, dir_count):
        total = file_count + dir_count
        if total == 0:
            self.setSuccessinfo("扫描完成，没有找到需要清理的文件")
        else:
            self.setSuccessinfo(f"扫描完成，共找到 {total} 个文件/文件夹")
        self.bar_progress.setValue(100)

    def on_scan_error(self, error_msg):
        self.setWarninginfo(f"扫描出错：{error_msg}")

    def toggle_select_all(self, state):
        if state == Qt.Checked:
            for row in range(self.table_files.rowCount()):
                item = self.table_files.item(row, 0)
                if item:
                    item.setCheckState(Qt.Checked)
        else:
            for row in range(self.table_files.rowCount()):
                item = self.table_files.item(row, 0)
                if item:
                    item.setCheckState(Qt.Unchecked)

    def execute_delete(self):
        selected_files = []
        selected_dirs = []
        
        for row in range(self.table_files.rowCount()):
            item = self.table_files.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                file_info = self.file_data[row]
                if file_info["type"] == "file":
                    selected_files.append(file_info["path"])
                else:
                    selected_dirs.append(file_info["path"])
        
        if len(selected_files) + len(selected_dirs) == 0:
            self.setWarninginfo("请先选择要删除的文件")
            return
        
        self.setSuccessinfo("正在删除选中的文件...")
        
        self.total_file = len(selected_files)
        self.total_dir = len(selected_dirs)
        
        share_thread_arr = [0]
        
        if len(selected_files) + len(selected_dirs) > 0:
            thread = multiDeleteThread(selected_files, selected_dirs, share_thread_arr)
            thread.delete_process_signal.connect(self.callback)
            thread.start()
            
            self.remove_deleted_rows(selected_files, selected_dirs)

    def remove_deleted_rows(self, deleted_files, deleted_dirs):
        rows_to_remove = []
        for row in range(self.table_files.rowCount()):
            file_info = self.file_data[row]
            if file_info["path"] in deleted_files or file_info["path"] in deleted_dirs:
                rows_to_remove.append(row)
        
        for row in sorted(rows_to_remove, reverse=True):
            self.table_files.removeRow(row)
            del self.file_data[row]

    def get_fileNum(self, path, day, picCacheCheck, fileCheck, picCheck,
                    videoCheck, file_list, dir_list):
        dir_name = PureWindowsPath(path)
        correct_path = Path(dir_name)
        now = datetime.datetime.now()
        if picCacheCheck:
            path_one = correct_path / 'Attachment'
            path_two = correct_path / 'FileStorage/Cache'
            self.getPathFileNum(now, day, path_one, path_two, file_list,
                                dir_list)
        if fileCheck:
            path_one = correct_path / 'Files'
            path_two = correct_path / 'FileStorage/File'
            self.getPathFileNum(now, day, path_one, path_two, file_list,
                                dir_list)
        if picCheck:
            path_one = correct_path / 'Image/Image'
            path_two = correct_path / 'FileStorage/Image'
            self.getPathFileNum(now, day, path_one, path_two, file_list,
                                dir_list)
        if videoCheck:
            path_one = correct_path / 'Video'
            path_two = correct_path / 'FileStorage/Video'
            self.getPathFileNum(now, day, path_one, path_two, file_list,
                                dir_list)

    def pathFileDeal(self, now, day, path, file_list, dir_list):
        if os.path.exists(path):
            filelist = [
                f for f in os.listdir(path)
                if os.path.isfile(os.path.join(path, f))
            ]
            for i in range(0, len(filelist)):
                file_path = os.path.join(path, filelist[i])
                if os.path.isdir(file_path):
                    continue
                timestamp = datetime.datetime.fromtimestamp(
                    os.path.getmtime(file_path))
                diff = (now - timestamp).days
                if diff >= day:
                    file_list.append(file_path)

    def getPathFileNum(self, now, day, path_one, path_two, file_list,
                       dir_list):
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
                file_path = os.path.join(path_two, dirlist[i])
                if os.path.isfile(file_path):
                    continue
                if re.match('\d{4}(\-)\d{2}', dirlist[i]) != None:
                    cyear = int(dirlist[i].split('-', 1)[0])
                    cmonth = int(dirlist[i].split('-', 1)[1])
                    if self.__before_deadline(cyear, cmonth, td_year,
                                              td_month):
                        dir_list.append(file_path)
                    else:
                        if cmonth == td_month:
                            self.pathFileDeal(now, day, file_path, file_list,
                                              dir_list)

    def __before_deadline(self, cyear, cmonth, td_year, td_month):
        if cyear < td_year:
            return True
        elif cyear > td_year:
            return False
        elif cyear == td_year:
            return cmonth < td_month

    def callback(self, v):
        value = v / int((self.total_file + self.total_dir)) * 100
        self.bar_progress.setValue(int(value))
        if value == 100:
            out = "本次共清理文件" + str(self.total_file) + "个，文件夹" + str(
                self.total_dir) + "个。\n请前往回收站检查并清空。"
            self.setSuccessinfo(out)
            return

    def justdoit(self): 
        fd = open(working_dir + "/config.json", encoding="utf-8")
        self.config = json.load(fd)
        i = 0
        need_clean = False
        thread_list = []
        total_file = 0
        total_dir = 0
        share_thread_arr = [0]
        for value in self.config["users"]:
            file_list = []
            dir_list = []
            if value["is_clean"]:
                self.get_fileNum(self.config["data_dir"][i],
                                 int(value["clean_days"]),
                                 value["clean_pic_cache"], value["clean_file"],
                                 value["clean_pic"], value["clean_video"],
                                 file_list, dir_list)

            if len(file_list) + len(dir_list) != 0:
                need_clean = True
                total_file += len(file_list)
                total_dir += len(dir_list)
                thread_list.append(
                    multiDeleteThread(file_list, dir_list, share_thread_arr))
                thread_list[-1].delete_process_signal.connect(self.callback)
            i = i + 1

        if not need_clean:
            self.setWarninginfo("没有需要清理的文件")
        else:
            self.total_file = total_file
            self.total_dir = total_dir
            for thread in thread_list:
                thread.start()

    def show_config_window(self):
        self.config_window = ConfigWindow()
        self.setSuccessinfo("已经准备好，可以开始了！")

    def __init__(self):
        super().__init__()
        loadUi(working_dir + "/images/main.ui", self)

        self._frame()
        self._eventfilter()
        self.init_table()
        
        self.check_select_all.stateChanged.connect(self.toggle_select_all)
        
        self.doFadeIn()
        self.config_exists = True
        self.show()

        if not os.path.exists(working_dir + "/config.json"):
            self.setWarninginfo("首次使用，即将自动弹出配置窗口")
            self.config_exists = False

            timer = QTimer(self)
            timer.timeout.connect(self.show_config_window)
            timer.setSingleShot(True)
            
            timer.start(1000)


if __name__ == '__main__':
    app = QApplication([])
    win = MainWindow()
    app.exec_()
