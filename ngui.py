import sys

from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsDropShadowEffect, QListWidgetItem, QListView, QWidget, \
    QLabel, QHBoxLayout, QFileDialog
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal, QMutex, QSize, QEvent, QPoint
from PyQt5.QtGui import QMouseEvent, QCursor, QColor
from PyQt5.uic import loadUi

from pathlib import Path, PureWindowsPath
from dateutil import relativedelta
import os, datetime, time, re, math, resources, shutil, json

from deleteThread import *
from multiDeleteThread import multiDeleteThread
from selectVersion import *
from selectVersion import check_dir, existing_user_config

working_dir = os.path.split(os.path.realpath(__file__))[0]


# 主窗口
class Window(QMainWindow):

    def mousePressEvent(self, event):
        # 重写一堆方法使其支持拖动
        if event.button() == Qt.LeftButton:
            self.m_drag = True
            self.m_DragPosition = event.globalPos() - self.pos()
            event.accept()
            # self.setCursor(QCursor(Qt.OpenHandCursor))

    def mouseMoveEvent(self, QMouseEvent):
        try:
            if Qt.LeftButton and self.m_drag:
                self.move(QMouseEvent.globalPos() - self.m_DragPosition)
                QMouseEvent.accept()
        except:
            pass

    def mouseReleaseEvent(self, QMouseEvent):
        self.m_drag = False
        # self.setCursor(QCursor(Qt.ArrowCursor))

    def _frame(self):
        # 边框
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # 阴影
        effect = QGraphicsDropShadowEffect(blurRadius=12, xOffset=0, yOffset=0)
        effect.setColor(QColor(25, 25, 25, 170))
        self.mainFrame.setGraphicsEffect(effect)

    def doFadeIn(self):
        # 动画
        self.animation = QPropertyAnimation(self, b'windowOpacity')
        # 持续时间250ms
        self.animation.setDuration(250)
        try:
            # 尝试先取消动画完成后关闭窗口的信号
            self.animation.finished.disconnect(self.close)
        except:
            pass
        self.animation.stop()
        # 透明度范围从0逐渐增加到1
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.start()

    def doFadeOut(self):
        self.animation.stop()
        # 动画完成则关闭窗口
        self.animation.finished.connect(self.close)
        # 透明度范围从1逐渐减少到0s
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.start()

    def setWarninginfo(self, text):
        self.lab_info.setStyleSheet(
            """
            .QLabel {
                border:1px solid #ffccc7;
                border-radius:3px;
                line-height: 140px;
                padding: 5px;
                color: #434343;
                background: #fff2f0;
            }
            """
        )
        self.lab_info.setText(text)

    def setSuccessinfo(self, text):
        self.lab_info.setStyleSheet(
            """
            .QLabel {
                border:1px solid #b7eb8f;
                border-radius:3px;
                line-height: 140px;
                padding: 5px;
                color: #434343;
                background: #f6ffed;
            }
            """
        )
        self.lab_info.setText(text)


class ConfigWindow(Window):
    Signal_OneParameter = pyqtSignal(int)

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
            user_list = [elem for elem in list_ if elem != 'All Users' and elem != 'Applet']
            # 如果已有用户配置，那么写入新的用户配置，否则默认写入新配置
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
                        "is_clean": False,
                        "clean_pic_cache": True,
                        "clean_file": True,
                        "clean_pic": True,
                        "clean_video": True,
                        "is_timer": True,
                        "timer": "0h"
                    })

            config = {
                "data_dir": dir_list,
                "users": user_config
            }

            with open(working_dir + "/config.json", "w", encoding="utf-8") as f:
                json.dump(config, f)
            self.load_config()
        else:
            self.setWarninginfo('请选择正确的文件夹！一般是WeChat Files文件夹。')

    def save_config(self):
        self.update_config()
        self.doFadeOut()

    def check_wechat_exists(self):
        self.selectVersion = selectVersion()
        self.version_scan = self.selectVersion.getAllPath()[0]
        self.users_scan = self.selectVersion.getAllPath()[1]
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

        self.line_gobackdays.setText(str(self.config["users"][0]["clean_days"]))
        self.check_is_clean.setChecked(self.config["users"][0]["is_clean"])
        self.check_picdown.setChecked(self.config["users"][0]["clean_pic"])
        self.check_files.setChecked(self.config["users"][0]["clean_file"])
        self.check_video.setChecked(self.config["users"][0]["clean_video"])
        self.check_picscache.setChecked(self.config["users"][0]["clean_pic_cache"])
        self.setSuccessinfo("加载配置文件成功")

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
        true = True
        if not os.path.exists(working_dir + "/config.json"):
            if not self.check_wechat_exists():
                if os.path.exists(self.openfile_name):
                    dirlist = []
                    list_ = os.listdir(self.openfile_name)
                    list_.remove('All Users')
                    list_.remove('Applet')
                    for i in range(0, len(list_)):
                        file_path = os.path.join(self.openfile_name, list_[i])
                        if os.path.isdir(file_path):
                            dirlist.append(file_path)
                    self.version_scan = dirlist
                    self.users_scan = list_
                    self.setSuccessinfo("扫描目录成功")
                else:
                    if self.openfile_name == "":
                        self.setWarninginfo("默认位置没有微信，请自定义位置")
                    else:
                        self.setWarninginfo("目录非微信数据目录，请检查")
                    return

            self.config = {
                "data_dir": self.version_scan,
                "users": []
            }
            for value in self.users_scan:
                self.config["users"].append({
                    "wechat_id": value,
                    "clean_days": 365,
                    "is_clean": False,
                    "clean_pic_cache": true,
                    "clean_file": False,
                    "clean_pic": true,
                    "clean_video": true,
                    "is_timer": true,
                    "timer": "0h"
                })
            with open(working_dir + "/config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f)
            self.load_config()
            self.setSuccessinfo("加载配置文件成功")
        else:
            self.setSuccessinfo("加载配置文件成功")
            self.load_config()

    def update_config(self):
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
        
        with open(working_dir+"/config.json","w",encoding="utf-8") as f:
            json.dump(self.config,f)
        self.setSuccessinfo("更新配置文件成功")
        self.Signal_OneParameter.emit(1)

    def __init__(self):
        super().__init__()
        loadUi(working_dir + "/ui/config.ui", self)

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
        sys.exit(0)

    def eventFilter(self, object, event):
        if event.type() == QEvent.MouseButtonPress:
            if object == self.lab_close:
                self.doFadeOut()
                return True
            elif object == self.lab_clean:
                try:
                    self.setSuccessinfo("正在清理中...")
                    self.justdoit()
                except:
                    self.setWarninginfo("清理失败，请检查配置文件后重试")
                return True
            elif object == self.lab_config:
                cw = ConfigWindow()
                cw.Signal_OneParameter.connect(self.deal_emit_slot)
                return True
        return False

    def _eventfilter(self):
        # 事件过滤
        self.lab_close.installEventFilter(self)
        self.lab_clean.installEventFilter(self)
        self.lab_config.installEventFilter(self)

    def get_fileNum(self, path, day, picCacheCheck, fileCheck, picCheck,
                    videoCheck, file_list, dir_list):
        dir_name = PureWindowsPath(path)
        # Convert path to the right format for the current operating system
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
        if os.path.exists(path):
            filelist = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
            for i in range(0, len(filelist)):
                file_path = os.path.join(path, filelist[i])
                if os.path.isdir(file_path):
                    continue
                timestamp = datetime.datetime.fromtimestamp(
                    os.path.getmtime(file_path))
                diff = (now - timestamp).days
                if diff >= day:
                    file_list.append(file_path)

    def getPathFileNum(self, now, day, path_one, path_two, file_list, dir_list):
        # caculate path_one
        self.pathFileDeal(now, day, path_one, file_list, dir_list)
        td = datetime.datetime.now() - datetime.timedelta(days=day)
        td_year =  td.year
        td_month = td.month
        # caculate path_two
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
                    if self.__before_deadline(cyear, cmonth, td_year, td_month):
                        dir_list.append(file_path)
                    else:
                        if cmonth == td_month:
                            self.pathFileDeal(now, day, file_path, file_list, dir_list)

    def __before_deadline(self,cyear, cmonth, td_year, td_month):
        if cyear < td_year:
            return True
        else:
            return cmonth < td_month

    def callback(self, v):
        value = v / int((self.total_file + self.total_dir)) * 100
        self.bar_progress.setValue(value)
        if value == 100:
            out = "本次共清理文件" + str(self.total_file) + "个，文件夹" + str(self.total_dir) + "个。请前往回收站检查并清空。"
            self.setSuccessinfo(out)
            return

    def justdoit(self):  # 这个Api设计的太脑残了，其实dir可以直接放在user里的... 有时间改吧
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
                self.get_fileNum(self.config["data_dir"][i], int(value["clean_days"]), value["clean_pic_cache"],
                                 value["clean_file"], value["clean_pic"], value["clean_video"], file_list, dir_list)

            if len(file_list) + len(dir_list) != 0:
                need_clean = True
                total_file += len(file_list)
                total_dir += len(dir_list)
                thread_list.append(multiDeleteThread(file_list, dir_list, share_thread_arr))
                thread_list[-1].delete_process_signal.connect(self.callback)
            i = i + 1

        if not need_clean:
            self.setWarninginfo("没有需要清理的文件")
        else:
            self.total_file = total_file
            self.total_dir = total_dir
            for thread in thread_list:
                thread.run()

    def __init__(self):
        super().__init__()
        loadUi(working_dir + "/ui/main.ui", self)

        self._frame()
        self._eventfilter()
        self.doFadeIn()

        # 判断配置文件是否存在
        if not os.path.exists(working_dir + "/config.json"):
            self.setWarninginfo("配置文件不存在！请单击“设置”创建配置文件")
            self.config_exists = False

        self.show()


if __name__ == '__main__':
    app = QApplication([])
    win = MainWindow()
    app.exec_()
