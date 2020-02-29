# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'autodelete.ui'
#
# Created by: PyQt5 UI code generator 5.13.0
#
# WARNING! All changes made in this file will be lost!

import os, datetime, time, re, math
import shutil

from PyQt5.QtCore import QBasicTimer
from dateutil import relativedelta
from pathlib import Path, PureWindowsPath
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMessageBox, QProgressBar  # QmessageBox是弹出框函数

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QDialog, QProgressBar, QPushButton)

from selectVersion import *
from deleteThread import *
from loadPath import *


class Ui_MainWin(object):
    def setupUi(self, MainWin):
        MainWin.setObjectName("MainWin")
        MainWin.resize(427, 175)
        self.centralwidget = QtWidgets.QWidget(MainWin)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName("gridLayout")

        self.lineEdit = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit.setMinimumSize(QtCore.QSize(0, 0))
        self.lineEdit.setText("")
        self.loadpath = loadPath()
        temp = self.loadpath.load()
        if temp != '':
            self.lineEdit.setText(temp)
        self.lineEdit.setObjectName("lineEdit")
        self.gridLayout.addWidget(self.lineEdit, 0, 1, 1, 2)

        self.lineEdit_2 = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_2.setObjectName("lineEdit_2")
        self.gridLayout.addWidget(self.lineEdit_2, 2, 1, 1, 1)

        self.checkBox = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox.setEnabled(True)
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.checkBox.setFont(font)
        self.checkBox.setChecked(True)
        self.checkBox.setObjectName("checkBox")
        self.gridLayout.addWidget(self.checkBox, 3, 1, 1, 2)

        self.checkBox_2 = QtWidgets.QCheckBox(self.centralwidget)
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.checkBox_2.setFont(font)
        self.checkBox_2.setChecked(True)
        self.checkBox_2.setObjectName("checkBox_2")
        self.gridLayout.addWidget(self.checkBox_2, 4, 1, 1, 2)

        self.checkBox_3 = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_3.setMinimumSize(QtCore.QSize(0, 0))
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.checkBox_3.setFont(font)
        self.checkBox_3.setChecked(True)
        self.checkBox_3.setObjectName("checkBox_3")
        self.gridLayout.addWidget(self.checkBox_3, 5, 1, 1, 2)

        self.checkBox_4 = QtWidgets.QCheckBox(self.centralwidget)
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.checkBox_4.setFont(font)
        self.checkBox_4.setChecked(True)
        self.checkBox_4.setObjectName("checkBox_4")
        self.gridLayout.addWidget(self.checkBox_4, 6, 1, 1, 2)

        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)

        self.progress = QProgressBar(self)
        self.gridLayout.addWidget(self.progress, 7, 0)
        self.progress.setMaximum(100)

        self.label = QtWidgets.QLabel(self.centralwidget)
        font = QtGui.QFont()
        font.setFamily("宋体")
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.label.setFont(font)
        self.label.setTextFormat(QtCore.Qt.AutoText)
        self.label.setObjectName("label")
        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.label_4 = QtWidgets.QLabel(self.centralwidget)
        font = QtGui.QFont()
        font.setFamily("宋体")
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.label_4.setFont(font)
        self.label_4.setTextFormat(QtCore.Qt.AutoText)
        self.label_4.setObjectName("label_4")
        self.gridLayout.addWidget(self.label_4, 3, 0, 1, 1)
        self.label_8 = QtWidgets.QLabel(self.centralwidget)
        font = QtGui.QFont()
        font.setFamily("宋体")
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.label_8.setFont(font)
        self.label_8.setTextFormat(QtCore.Qt.AutoText)
        self.label_8.setObjectName("label_8")
        self.gridLayout.addWidget(self.label_8, 6, 0, 1, 1)

        self.pushButton = QtWidgets.QPushButton(self.centralwidget)
        font = QtGui.QFont()
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.pushButton.setFont(font)
        self.pushButton.setObjectName("pushButton")
        self.gridLayout.addWidget(self.pushButton, 7, 1, 1, 1)
        self.pushButton.clicked.connect(self.confirm)

        self.label_3 = QtWidgets.QLabel(self.centralwidget)
        font = QtGui.QFont()
        font.setFamily("宋体")
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.label_3.setFont(font)
        self.label_3.setTextFormat(QtCore.Qt.AutoText)
        self.label_3.setObjectName("label_3")
        self.gridLayout.addWidget(self.label_3, 2, 2, 1, 1)

        self.label_2 = QtWidgets.QLabel(self.centralwidget)
        font = QtGui.QFont()
        font.setFamily("宋体")
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.label_2.setFont(font)
        self.label_2.setTextFormat(QtCore.Qt.AutoText)
        self.label_2.setObjectName("label_2")
        self.gridLayout.addWidget(self.label_2, 2, 0, 1, 1)
        self.label_6 = QtWidgets.QLabel(self.centralwidget)
        self.label_6.setAlignment(QtCore.Qt.AlignCenter)
        self.label_6.setObjectName("label_6")
        self.label_6.setOpenExternalLinks(True)
        self.gridLayout.addWidget(self.label_6, 10, 0, 1, 3)
        self.label_7 = QtWidgets.QLabel(self.centralwidget)
        self.label_7.setText("")
        self.label_7.setObjectName("label_7")
        self.gridLayout.addWidget(self.label_7, 9, 0, 1, 1)
        MainWin.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWin)
        QtCore.QMetaObject.connectSlotsByName(MainWin)

    def confirm(self):
        self.fileList = []
        self.dirList = []
        if self.lineEdit_2.text() == '':
            QMessageBox.critical(
                self,  #使用infomation信息框  
                "缺少天数",
                "请输入需要删除多久以前的文件")
            return
        if self.pushButton.isEnabled():
            self.day = int(self.lineEdit_2.text())
            self.picCacheCheck = self.checkBox.isChecked()
            self.fileCheck = self.checkBox_2.isChecked()
            self.picCheck = self.checkBox_3.isChecked()
            self.videoCheck = self.checkBox_4.isChecked()

            # 输入自定义路径
            if self.lineEdit.text() != '':
                self.path = self.lineEdit.text()
                if not os.path.exists(self.path):
                    QMessageBox.critical(
                        self,  # 使用infomation信息框
                        "路径不存在",
                        "请检查输入路径是否正确")
                    return
                self.loadpath.storage(self.path)
                self.getFileNum(self.path, self.day, self.picCacheCheck,
                                self.fileCheck, self.picCheck, self.videoCheck)
                # 增加0边界处理
                if len(self.fileList) + len(self.dirList) == 0:
                    out = "没有需要清理的文件。"
                    QMessageBox.information(
                        self,  # 使用infomation信息框
                        "清理完成",
                        out)
                    return
                self.onButtonClick()
            # 使用默认安装路径
            else:
                self.selectVersion = selectVersion()
                # 获取当前版本
                self.version = self.selectVersion.getAllPath()
                # 三个版本的路径均未找到， 则用户使用的应该是自定义路径
                if len(self.version) == 0:
                    QMessageBox.critical(
                        self,  # 使用infomation信息框
                        "默认路径错误",
                        "您的微信使用了自定义路径，请输入自定义路径。")
                    return
                for value in self.version:
                    self.getFileNum(value, self.day, self.picCacheCheck,
                                    self.fileCheck, self.picCheck,
                                    self.videoCheck)
                # 增加0边界处理
                if len(self.fileList) + len(self.dirList) == 0:
                    out = "没有需要清理的文件。"
                    QMessageBox.information(
                        self,  # 使用infomation信息框
                        "清理完成",
                        out)
                    return
                self.onButtonClick()

    def retranslateUi(self, MainWin):
        _translate = QtCore.QCoreApplication.translate
        MainWin.setWindowTitle(_translate("MainWin", "微信客户端数据自动删除工具V1.2"))
        # icon = QtGui.QIcon()
        # # change to your own icon path
        # icon.addPixmap(
        #     QtGui.QPixmap("C:\Project\AutoDeleteFileOnPCWechat\icon.ico"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        # MainWin.setWindowIcon(icon)
        self.checkBox_4.setText(_translate("MainWin", "视频（视频文件和视频的封面图）"))
        self.label.setText(_translate("MainWin", "工具会自动识别路径，若自定义存储路径请填写："))
        self.lineEdit_2.setText(_translate("MainWin", "365"))
        self.lineEdit_2.setValidator(QtGui.QIntValidator())  #设置只能输入int类型的数据
        self.label_4.setText(_translate("MainWin", "想要删除的文件类型："))
        self.label_8.setText(_translate("MainWin", "删除进度："))
        self.pushButton.setText(_translate("MainWin", "确定"))
        self.checkBox_2.setText(
            _translate("MainWin", "文件（PPT,Word,gif,PDF 等）"))
        self.lineEdit.setPlaceholderText(
            _translate("MainWin",
                       "类似C:\\Users\\xx\\Documents\\WeChat Files\\xx"))
        self.label_3.setText(_translate("MainWin", "天前"))
        self.checkBox.setText(_translate("MainWin", "图片类缓存（来自小程序、公众号等）"))
        self.checkBox_3.setText(_translate("MainWin", "图片（JPG 等）"))
        self.label_2.setText(_translate("MainWin", "需要删除多久以前的文件："))
        self.label_6.setText(
            u'<a href="https://www.blackboxo.top" style="color:#000000;">Made by blackboxo</a>'
        )


    #获得不同路径下的文件总数
    def getFileNum(self, path, day, picCacheCheck, fileCheck, picCheck,
                   videoCheck):
        dirname = PureWindowsPath(path)
        # Convert path to the right format for the current operating system
        correct_path = Path(dirname)
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
                    self.fileList.append(file_path)

    #获得该路径下的文件数目
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
                        self.dirList.append(file_path)
                    elif diff == month:
                        self.pathFileDeal(now, day, file_path)
                        # print("delete:", file_path)

    #进度条事件
    def onButtonClick(self):
        #另起一个线程来实现删除文件和更新进度条
        self.calc = deleteThread(self.fileList, self.dirList)
        self.calc.delete_proess_signal.connect(self.onCountChanged)
        self.calc.start()

    def onCountChanged(self, value):
        self.progress.setValue(value)
        if value == 100:
            out = "本次共清理文件" + str(len(self.fileList)) + "个，文件夹" + str(
                len(self.dirList)) + "个。请前往回收站检查并清空。"
            QMessageBox.information(
                self,  #使用infomation信息框
                "清理完成",
                out)
            return
