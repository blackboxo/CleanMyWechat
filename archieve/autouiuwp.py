# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'autodeleteforuwp.ui'
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
from PyQt5.QtWidgets import QMessageBox, QProgressBar  # QmessageBox是弹出框函数

from deleteThread import *


class Ui_MainWin(object):
    def setupUi(self, MainWin):
        MainWin.setObjectName("MainWin")
        MainWin.resize(450, 232)
        self.centralwidget = QtWidgets.QWidget(MainWin)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName("gridLayout")
        self.lineEdit = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit.setMinimumSize(QtCore.QSize(0, 0))
        self.lineEdit.setText("")
        self.lineEdit.setPlaceholderText("")
        self.lineEdit.setObjectName("lineEdit")
        self.gridLayout.addWidget(self.lineEdit, 0, 1, 1, 2)

        self.lineEdit_3 = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_3.setObjectName("lineEdit_3")
        self.gridLayout.addWidget(self.lineEdit_3, 1, 1, 1, 2)

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
        self.pushButton = QtWidgets.QPushButton(self.centralwidget)
        font = QtGui.QFont()
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.pushButton.setFont(font)
        self.pushButton.setObjectName("pushButton")
        self.gridLayout.addWidget(self.pushButton, 7, 1, 1, 1)
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

        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.progress = QProgressBar(self)
        self.gridLayout.addWidget(self.progress, 6, 0)
        self.progress.setMaximum(100)



        self.label_6 = QtWidgets.QLabel(self.centralwidget)
        self.label_6.setAlignment(QtCore.Qt.AlignCenter)
        self.label_6.setOpenExternalLinks(True)
        self.label_6.setObjectName("label_6")
        self.gridLayout.addWidget(self.label_6, 10, 0, 1, 3)

        self.label_7 = QtWidgets.QLabel(self.centralwidget)
        self.label_7.setText("")
        self.label_7.setObjectName("label_7")
        self.gridLayout.addWidget(self.label_7, 9, 0, 1, 1)

        self.label_8 = QtWidgets.QLabel(self.centralwidget)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label_8.setFont(font)
        self.label_8.setObjectName("label_8")
        self.gridLayout.addWidget(self.label_8, 1, 0, 1, 1)

        self.pushButton.clicked.connect(self.confirm)
        self.label_6.setOpenExternalLinks(True)
        MainWin.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWin)
        QtCore.QMetaObject.connectSlotsByName(MainWin)

    def confirm(self):
        self.fileNum = 0
        self.dirNum = 0
        if self.lineEdit.text() == '':
            QMessageBox.critical(
                self,  #使用infomation信息框  
                "缺少用户名",
                "请输入电脑的用户名")
        elif self.lineEdit_3.text() == '':
            QMessageBox.critical(
                self,  #使用infomation信息框  
                "缺少微信号",
                "请输入微信号")
        elif self.lineEdit_2.text() == '':
            QMessageBox.critical(
                self,  #使用infomation信息框  
                "缺少月份",
                "请输入需要删除多久以前的文件")
        elif self.pushButton.isEnabled():
            self.path = 'C:\\Users\\' + self.lineEdit.text(
            ) + '\\AppData\\Local\\Packages\\TencentWeChatLimited.forWindows10_sdtnhv12zgd7a\\LocalCache\\Roaming\\Tencent\\WeChatAppStore\\WeChatAppStore Files\\' + self.lineEdit_3.text(
            )
            print(self.path)
            if not os.path.exists(self.path):
                QMessageBox.critical(
                    self,  #使用infomation信息框  
                    "路径错误",
                    "文件夹不存在，请检查用户名和微信号")
            else:
                self.month = int(self.lineEdit_2.text())
                self.picCacheCheck = self.checkBox.isChecked()
                self.fileCheck = self.checkBox_2.isChecked()
                self.picCheck = self.checkBox_3.isChecked()
                self.videoCheck = self.checkBox_4.isChecked()

                self.getFileNum(self.path, self.month, self.picCacheCheck, self.fileCheck, self.picCheck,
                                self.videoCheck)
                #增加0边界处理
                if self.fileNum == 0:
                    out = "本次共清理文件" + str(self.fileNum) + "个。"
                    QMessageBox.information(
                        self,  #使用infomation信息框
                        "清理完成",
                        out)
                    return
                self.onButtonClick()
                # if self.picCacheCheck:
                #     self.deleteFile(path, month, "piccache")
                # if self.fileCheck:
                #     self.deleteFile(path, month, "file")
                # if self.picCheck:
                #     self.deleteFile(path, month, "pic")
                # if self.videoCheck:
                #     self.deleteFile(path, month, "video")

                # out = "本次共清理文件" + str(self.fileNum) + "个。请前往回收站检查并清空。"
                # QMessageBox.information(
                #     self,  #使用infomation信息框
                #     "清理完成",
                #     out)

    # def deleteFile(self, path, month, type):
    #     dirname = path
    #     # Convert path to the right format for the current operating system
    #     correct_path = Path(dirname)
    #     now = datetime.datetime.now()
    #     if type == "piccache":
    #         path_one = correct_path / 'Attachment'
    #     elif type == "file":
    #         path_one = correct_path / 'Files'
    #     elif type == "pic":
    #         path_one = correct_path / 'Image/Image'
    #     elif type == "video":
    #         path_one = correct_path / 'Video'
    #
    #     # Delete path_one
    #     if os.path.exists(path_one):
    #         list = os.listdir(path_one)
    #         filelist = []
    #         for i in range(0, len(list)):
    #             file_path = os.path.join(path_one, list[i])
    #             if os.path.isfile(file_path):
    #                 filelist.append(list[i])
    #         for i in range(0, len(filelist)):
    #             file_path = os.path.join(path_one, filelist[i])
    #             if os.path.isdir(file_path):
    #                 continue
    #             timestamp = datetime.datetime.fromtimestamp(
    #                 os.path.getmtime(file_path))
    #             r = relativedelta.relativedelta(now, timestamp)
    #             if r.years * 12 + r.months > month:
    #                 send2trash(file_path)
    #                 self.fileNum = self.fileNum + 1



    def retranslateUi(self, MainWin):
        _translate = QtCore.QCoreApplication.translate
        MainWin.setWindowTitle(_translate("MainWin", "微信for Windows数据自动删除工具"))
        self.checkBox.setText(_translate("MainWin", "图片类缓存"))
        self.label_4.setText(_translate("MainWin", "想要删除的文件类型："))
        self.label_2.setText(_translate("MainWin", "需要删除多久以前的文件："))
        self.lineEdit_2.setValidator(QtGui.QIntValidator())  #设置只能输入int类型的数据
        self.pushButton.setText(_translate("MainWin", "确定"))
        self.label_3.setText(_translate("MainWin", "个月前"))
        self.label.setText(_translate("MainWin", "请输入你的电脑的用户名："))
        self.checkBox_4.setText(_translate("MainWin", "视频（视频文件和视频的封面图）"))
        self.lineEdit_2.setText(_translate("MainWin", "24"))
        self.label_6.setText(_translate("MainWin", "Made by blackboxo"))
        self.checkBox_3.setText(_translate("MainWin", "图片（JPG 等）"))
        self.checkBox_2.setText(
            _translate("MainWin", "文件（PPT,Word,gif,PDF 等）"))
        self.label_8.setText(_translate("MainWin", "请输入你的微信号（不是微信名）"))
        self.label_6.setText(
            u'<a href="https://github.com/blackboxo/AutoDeleteFileOnPCWechat" style="color:#000000;">Made by blackboxo</a>'
        )
        icon = QtGui.QIcon()
        icon.addPixmap(
            QtGui.QPixmap("icon.ico"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        MainWin.setWindowIcon(icon)

   #获得不同路径下的文件总数
    def getFileNum(self, path, month, picCacheCheck, fileCheck, picCheck, videoCheck):

        dirname = path
        # Convert path to the right format for the current operating system
        correct_path = Path(dirname)
        now = datetime.datetime.now()
        # if type == "piccache":
        #     path_one = correct_path / 'Attachment'
        # elif type == "file":
        #     path_one = correct_path / 'Files'
        # elif type == "pic":
        #     path_one = correct_path / 'Image/Image'
        # elif type == "video":
        #     path_one = correct_path / 'Video'
        #
        # self.getPathFileNum(now, month, path_one)

        if picCacheCheck:
            path_one = correct_path / 'Attachment'
            self.getPathFileNum(now, month, path_one)
        if fileCheck:
            path_one = correct_path / 'Files'
            self.getPathFileNum(now, month, path_one)
        if picCheck:
            path_one = correct_path / 'Image/Image'
            self.getPathFileNum(now, month, path_one)
        if videoCheck:
            path_one = correct_path / 'Video'
            self.getPathFileNum(now, month, path_one)

    #获得该路径下的文件数目
    def getPathFileNum(self, now, month, path_one):
        # caculate path_one
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
                    self.fileNum = self.fileNum + 1

    #进度条事件
    def onButtonClick(self):
        #另起一个线程来实现删除文件和更新进度条
        self.calc = deleteThread(self.fileNum + self.dirNum, self.path, self.month, self.picCacheCheck, self.fileCheck, self.picCheck, self.videoCheck, True)
        self.calc.delete_proess_signal.connect(self.onCountChanged)
        self.calc.start()

    def onCountChanged(self, value):
        self.progress.setValue(value)
        if value == 100:
            out = "本次共清理文件" + str(self.fileNum) + "个。请前往回收站检查并清空。"
            QMessageBox.information(
                self,  # 使用infomation信息框
                "清理完成",
                out)
            return