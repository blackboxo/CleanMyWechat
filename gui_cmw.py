from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsDropShadowEffect, QListWidgetItem, QListView, QWidget, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal, QMutex, QSize, QEvent, QPoint
from PyQt5.QtGui import QMouseEvent, QCursor, QColor
from PyQt5.uic import loadUi

from pathlib import Path, PureWindowsPath
from dateutil import relativedelta
import os, datetime, time, re, math, resources, shutil, json

from deleteThread import *
import gui_config

working_dir = os.path.split(os.path.realpath(__file__))[0]

# 主窗口
class Window(QMainWindow):

    def mousePressEvent(self, event):
        # 重写一堆方法使其支持拖动
        if event.button()==Qt.LeftButton:
            self.m_drag=True
            self.m_DragPosition=event.globalPos()-self.pos()
            event.accept()
            #self.setCursor(QCursor(Qt.OpenHandCursor))
    def mouseMoveEvent(self, QMouseEvent):
        try:
            if Qt.LeftButton and self.m_drag:
                self.move(QMouseEvent.globalPos()-self.m_DragPosition)
                QMouseEvent.accept()
        except:
            pass
    def mouseReleaseEvent(self, QMouseEvent):
        self.m_drag=False
        #self.setCursor(QCursor(Qt.ArrowCursor))
    def eventFilter(self, object, event):
        if event.type() == QEvent.MouseButtonPress:
            if object == self.lab_close:
                self.doFadeOut()
                return True
            elif object == self.lab_clean:
                try:
                    self.justdoit()
                except:
                    self.setWarninfo("没有找到配置文件或配置文件错误，请打开设置")
                return True
            elif object == self.lab_config:
                win = gui_config.Window()
                return True
        return False

    def _frame(self):
        # 边框
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # 阴影
        effect = QGraphicsDropShadowEffect(blurRadius=12, xOffset=0, yOffset=0)
        effect.setColor(QColor(25, 25, 25, 170))
        self.mainFrame.setGraphicsEffect(effect)
    def _connect(self):
        # 信号
        #self.btn_close.clicked.connect(self.doFadeOut)
        return
    def _eventfilter(self):
        # 事件过滤
        self.lab_close.installEventFilter(self)
        self.lab_clean.installEventFilter(self)
        self.lab_config.installEventFilter(self)
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

    def get_fileNum(self, path, day, picCacheCheck, fileCheck, picCheck,
                   videoCheck):
        dir_name = PureWindowsPath(path)
        # Convert path to the right format for the current operating system
        correct_path = Path(dir_name)
        now = datetime.datetime.now()
        if picCacheCheck:
            path_one = correct_path / 'Attachment'
            path_two = correct_path / 'FileStorage/Cache'
            self.getPathFileNum(now, day, path_one, path_two)
        if fileCheck:
            path_one = correct_path / 'Files'
            path_two = correct_path / 'FileStorage/File'
            self.getPathFileNum(now, day, path_one, path_two)
        if picCheck:
            path_one = correct_path / 'Image/Image'
            path_two = correct_path / 'FileStorage/Image'
            self.getPathFileNum(now, day, path_one, path_two)
        if videoCheck:
            path_one = correct_path / 'Video'
            path_two = correct_path / 'FileStorage/Video'
            self.getPathFileNum(now, day, path_one, path_two)
    def pathFileDeal(self, now, day, path):
        if os.path.exists(path):
            list = os.listdir(path)
            filelist = []
            for i in range(0, len(list)):
                file_path = os.path.join(path, list[i])
                if os.path.isfile(file_path):
                    filelist.append(list[i])
            for i in range(0, len(filelist)):
                file_path = os.path.join(path, filelist[i])
                if os.path.isdir(file_path):
                    continue
                timestamp = datetime.datetime.fromtimestamp(
                    os.path.getmtime(file_path))
                #r = relativedelta.relativedelta(now, timestamp)
                #if r.years * 12 + r.months > month:
                diff = (now - timestamp).days
                if diff > day:
                    self.file_list.append(file_path)
    def getPathFileNum(self, now, day, path_one, path_two):
        # caculate path_one
        self.pathFileDeal(now, day, path_one)

        # caculate path_two
        if os.path.exists(path_two):
            osdir = os.listdir(path_two)
            dirlist = []
            month = math.ceil(day / 29)
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
                    diff = (now.year - cyear) * 12 + now.month - cmonth
                    if diff > month:
                        self.dir_list.append(file_path)
                    elif diff == month:
                        self.pathFileDeal(now, day, file_path)
                        #print("delete:", file_path)

    def callin(self):
        #另起一个线程来实现删除文件和更新进度条
        self.calc = deleteThread(self.file_list, self.dir_list)
        self.calc.delete_proess_signal.connect(self.callback)
        self.calc.start()
    def callback(self, value):
        self.bar_progress.setValue(value)
        if value == 100:
            out = "本次共清理文件" + str(len(self.file_list)) + "个，文件夹" + str(
                len(self.dir_list)) + "个。请前往回收站检查并清空。"
            self.setOKinfo(out)
            return
    
    def setWarninfo(self, text):
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
    def setOKinfo(self, text):
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

    def justdoit(self): # 这个Api设计的太脑残了，其实dir可以直接放在user里的... 有时间改吧
        self.file_list = []
        self.dir_list = []
        self.config = open(working_dir+"/config.json", encoding="utf-8")
        self.config = json.load(self.config)
        i = 0
        for value in self.config["users"]:
            if value["is_clean"]:
                self.get_fileNum(self.config["data_dir"][i], int(value["clean_days"]), value["clean_pic_cache"],value["clean_file"], value["clean_pic"], value["clean_video"])
            i = i + 1
                
            if len(self.file_list) + len(self.dir_list) == 0:
                self.setWarninfo("没有需要清理的文件（可能是您没打勾哦）")
                
            self.callin()

    def __init__(self):
        super().__init__()
        loadUi(working_dir+"/ui/main.ui", self)

        self._frame()
        #self._connect()
        self._eventfilter()
        self.doFadeIn()

        self.show()

if __name__ == '__main__':
    app = QApplication([])
    win = Window()
    app.exec_()