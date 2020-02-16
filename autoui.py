# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'autodelete.ui'
#
# Created by: PyQt5 UI code generator 5.13.0
#
# WARNING! All changes made in this file will be lost!

import os, datetime, time, re
import shutil
from dateutil import relativedelta
from send2trash import send2trash
from pathlib import Path, PureWindowsPath
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMessageBox  #QmessageBox是弹出框函数


class Ui_MainWin(object):
    def setupUi(self, MainWin):
        MainWin.setObjectName("MainWin")
        MainWin.resize(427, 175)
        self.centralwidget = QtWidgets.QWidget(MainWin)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName("gridLayout")
        self.checkBox_4 = QtWidgets.QCheckBox(self.centralwidget)
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.checkBox_4.setFont(font)
        self.checkBox_4.setChecked(True)
        self.checkBox_4.setObjectName("checkBox_4")
        self.gridLayout.addWidget(self.checkBox_4, 6, 1, 1, 2)
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
        self.lineEdit_2 = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_2.setObjectName("lineEdit_2")
        self.gridLayout.addWidget(self.lineEdit_2, 2, 1, 1, 1)
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
        self.pushButton = QtWidgets.QPushButton(self.centralwidget)
        font = QtGui.QFont()
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.pushButton.setFont(font)
        self.pushButton.setObjectName("pushButton")
        self.gridLayout.addWidget(self.pushButton, 7, 1, 1, 1)
        self.pushButton.clicked.connect(self.confirm)
        self.checkBox_2 = QtWidgets.QCheckBox(self.centralwidget)
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.checkBox_2.setFont(font)
        self.checkBox_2.setChecked(True)
        self.checkBox_2.setObjectName("checkBox_2")
        self.gridLayout.addWidget(self.checkBox_2, 4, 1, 1, 2)
        self.lineEdit = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit.setMinimumSize(QtCore.QSize(0, 0))
        self.lineEdit.setText("")
        self.lineEdit.setObjectName("lineEdit")
        self.gridLayout.addWidget(self.lineEdit, 0, 1, 1, 2)
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
        self.label_5 = QtWidgets.QLabel(self.centralwidget)
        self.label_5.setObjectName("label_5")
        self.gridLayout.addWidget(self.label_5, 1, 1, 1, 2)
        MainWin.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWin)
        QtCore.QMetaObject.connectSlotsByName(MainWin)

    def confirm(self):
        self.fileNum = 0
        self.dirNum = 0
        if self.pushButton.isEnabled() and self.lineEdit.text() != '':
            path = self.lineEdit.text()
            month = int(self.lineEdit_2.text())
            picCacheCheck = self.checkBox.isChecked()
            fileCheck = self.checkBox_2.isChecked()
            picCheck = self.checkBox_3.isChecked()
            videoCheck = self.checkBox_4.isChecked()
            if picCacheCheck:
                self.deleteFile(path, month, "piccache")
            if fileCheck:
                self.deleteFile(path, month, "file")
            if picCheck:
                self.deleteFile(path, month, "pic")
            if videoCheck:
                self.deleteFile(path, month, "video")

            out = "本次共清理文件" + str(self.fileNum) + "个，文件夹" + str(
                self.dirNum) + "个。请前往回收站检查并清空。"
            QMessageBox.information(
                self,  #使用infomation信息框  
                "清理完成",
                out)
        elif self.lineEdit_2.text() == '':
            QMessageBox.critical(
                self,  #使用infomation信息框  
                "缺少月份",
                "请输入需要删除多久以前的文件")
        else:
            QMessageBox.critical(
                self,  #使用infomation信息框  
                "缺失路径",
                "请输入微信文件的存储路径")

    def deleteFile(self, path, month, type):
        # I've explicitly declared my path as being in Windows format, so I can use forward slashes in it.
        dirname = PureWindowsPath(path)
        # Convert path to the right format for the current operating system
        correct_path = Path(dirname)
        now = datetime.datetime.now()
        if type == "piccache":
            path_one = correct_path / 'Attachment'
            path_two = correct_path / 'FileStorage/Cache'
        elif type == "file":
            path_one = correct_path / 'Files'
            path_two = correct_path / 'FileStorage/File'
        elif type == "pic":
            path_one = correct_path / 'Image/Image'
            path_two = correct_path / 'FileStorage/Image'
        elif type == "video":
            path_one = correct_path / 'Video'
            path_two = correct_path / 'FileStorage/Video'

        # Delete path_one
        if os.path.exists(path_one):
            list = os.listdir(path_one)
            filelist = []
            for i in range(0, len(list)):
                file_path = os.path.join(path_one, list[i])
                if os.path.isfile(file_path):
                    filelist.append(list[i])
            for i in range(0, len(filelist)):
                file_path = os.path.join(path_one, filelist[i])
                if os.path.isdir(file_path):
                    continue
                timestamp = datetime.datetime.fromtimestamp(
                    os.path.getmtime(file_path))
                r = relativedelta.relativedelta(now, timestamp)
                if r.years * 12 + r.months > month:
                    send2trash(file_path)
                    self.fileNum = self.fileNum + 1
                    # print("delete:", file_path)

        # Delete path_two
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
                    diff = (now.year - cyear) * 12 + now.month - cmonth
                    if diff > month:
                        send2trash(file_path)
                        self.dirNum = self.dirNum + 1
                        # print("delete:", file_path)

    def retranslateUi(self, MainWin):
        _translate = QtCore.QCoreApplication.translate
        MainWin.setWindowTitle(_translate("MainWin", "微信客户端数据自动删除工具"))
        self.checkBox_4.setText(_translate("MainWin", "视频（视频文件和视频的封面图）"))
        self.label.setText(_translate("MainWin", "请输入微信文件的存储路径："))
        self.lineEdit_2.setText(_translate("MainWin", "24"))
        self.lineEdit_2.setValidator(QtGui.QIntValidator())  #设置只能输入int类型的数据
        self.label_4.setText(_translate("MainWin", "想要删除的文件类型："))
        self.pushButton.setText(_translate("MainWin", "确定"))
        self.checkBox_2.setText(
            _translate("MainWin", "文件（PPT,Word,gif,PDF 等）"))
        self.lineEdit.setPlaceholderText(
            _translate("MainWin",
                       "类似C:\\Users\\xx\\Documents\\WeChat Files\\xx"))
        self.label_3.setText(_translate("MainWin", "个月前"))
        self.checkBox.setText(_translate("MainWin", "图片类缓存（来自小程序、公众号等）"))
        self.checkBox_3.setText(_translate("MainWin", "图片（JPG 等）"))
        self.label_2.setText(_translate("MainWin", "需要删除多久以前的文件："))
        self.label_5.setText(
            _translate("MainWin", "微信左下角->设置->通用设置->打开文件夹->复制路径"))
        self.label_6.setText(
            u'<a href="https://github.com/blackboxo/AutoDeleteFileOnPCWechat" style="color:#000000;">Made by blackboxo</a>'
        )
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("icon.ico"),QtGui.QIcon.Normal, QtGui.QIcon.Off)
        MainWin.setWindowIcon(icon)
