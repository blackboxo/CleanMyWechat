from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsDropShadowEffect, QListWidgetItem, QListView, QWidget, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal, QMutex, QSize, QEvent, QPoint
from PyQt5.QtGui import QMouseEvent, QCursor, QColor
from PyQt5.uic import loadUi
import os, resources, json

from selectVersion import *

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
        return False

    def _frame(self):
        # 边框
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # 阴影
        effect = QGraphicsDropShadowEffect(blurRadius=12, xOffset=0, yOffset=0)
        effect.setColor(QColor(25, 25, 25, 170))
        self.frame.setGraphicsEffect(effect)
    def _connect(self):
        self.combo_user.currentIndexChanged.connect(self.refresh_ui)
        self.line_wechat.textChanged.connect(self.create_config)
        self.btn_close.clicked.connect(self.doFadeOut)

        self.check_is_clean.stateChanged.connect(self.update_config)
        self.check_picdown.stateChanged.connect(self.update_config)
        self.check_files.stateChanged.connect(self.update_config)
        self.check_video.stateChanged.connect(self.update_config)
        self.check_picscache.stateChanged.connect(self.update_config)
        self.line_gobackdays.textChanged.connect(self.update_config)

    def _eventfilter(self):
        # 事件过滤
        pass
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

    def check_wechat_exists(self):
        self.selectVersion = selectVersion()
        self.version_scan = self.selectVersion.getAllPath()[0]
        self.users_scan = self.selectVersion.getAllPath()[1]
        if len(self.version_scan) == 0:
            return False
        else:
            return True

    def load_config(self):
        self.config = open(working_dir+"/config.json", encoding="utf-8")
        self.config = json.load(self.config)

        for value in self.config["users"]:
            self.combo_user.addItem(value["wechat_id"])

        self.line_gobackdays.setText(str(self.config["users"][0]["clean_days"]))
        self.check_is_clean.setChecked(self.config["users"][0]["is_clean"])
        self.check_picdown.setChecked(self.config["users"][0]["clean_pic"])
        self.check_files.setChecked(self.config["users"][0]["clean_file"]) 
        self.check_video.setChecked(self.config["users"][0]["clean_video"])
        self.check_picscache.setChecked(self.config["users"][0]["clean_pic_cache"])
        self.setOKinfo("加载配置文件成功")
    def refresh_ui(self):
        self.config = open(working_dir+"/config.json", encoding="utf-8")
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
        false = False
        if not os.path.exists(working_dir+"/config.json"): 
            if not self.check_wechat_exists():
                if os.path.exists(self.line_wechat.text()):
                    dirlist = []
                    list_ = os.listdir(self.line_wechat.text())
                    list_.remove('All Users')
                    list_.remove('Applet')
                    for i in range(0, len(list_)):
                        file_path = os.path.join(self.line_wechat.text(), list_[i])
                        if os.path.isdir(file_path):
                            dirlist.append(file_path)
                    self.version_scan = dirlist
                    self.users_scan = list_
                    self.setOKinfo("扫描目录成功")
                else:
                    if self.line_wechat.text() == "":
                        self.setWarninfo("默认位置没有微信，请自定义位置")
                    else:
                        self.setWarninfo("目录非微信数据目录，请检查")
                    return

            self.config = {
                "data_dir" : self.version_scan,
                "users" : []
            }
            for value in self.users_scan:
                self.config["users"].append({
                    "wechat_id" : value,
                    "clean_days": 365,
                    "is_clean": true,
                    "clean_pic_cache": true,
                    "clean_file": true,
                    "clean_pic": true,
                    "clean_video": true,
                    "is_timer": true,
                    "timer": "0h"
                })
            with open(working_dir+"/config.json","w",encoding="utf-8") as f:
                json.dump(self.config,f)
            self.setOKinfo("加载配置文件成功")
            self.load_config()
        else:
            self.setOKinfo("加载配置文件成功")
            self.load_config()
    def update_config(self):
        true = True
        false = False

        self.config = open(working_dir+"/config.json", encoding="utf-8")
        self.config = json.load(self.config)

        for value in self.config["users"]:
            if value["wechat_id"] == self.combo_user.currentText():
                value["clean_days"] = self.line_gobackdays.text()
                value["is_clean"] = self.check_is_clean.isChecked()
                value["clean_pic"] = self.check_picdown.isChecked() 
                value["clean_file"] = self.check_files.isChecked() 
                value["clean_video"] = self.check_video.isChecked() 
                value["clean_pic_cache"] = self.check_picscache.isChecked() 
        
        with open(working_dir+"/config.json","w",encoding="utf-8") as f:
            json.dump(self.config,f)
        self.setOKinfo("更新配置文件成功")

    def __init__(self):
        super().__init__()
        loadUi(working_dir+"/ui/config.ui", self)

        self._frame()
        self._eventfilter()
        self.doFadeIn()

        self.create_config()
        self._connect()

        self.show()

if __name__ == '__main__':
    app = QApplication([])
    win = Window()
    app.exec_()