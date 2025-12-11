import sys

from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsDropShadowEffect, QWidget, \
    QLabel, QHBoxLayout, QFileDialog, QTableWidget, QTableWidgetItem, QVBoxLayout, QPushButton, QCheckBox
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal, QEvent, QPoint, QTimer
from PyQt5.QtGui import QMouseEvent, QCursor, QColor

# 导入转换后的UI代码
from ui_main import Ui_MainWindow as MainWindowUI

from pathlib import Path, PureWindowsPath
import utils.resources
import os, datetime, time, re, math, shutil, json

from utils.multiDeleteThread import multiDeleteThread
from utils.selectVersion import check_dir, existing_user_config, selectVersion
# 设置应用程序在高DPI屏幕上启用高DPI缩放。Set the application to enable high DPI scaling on high DPI screens
# 注意事项：此行代码必须在QApplication实例化之前调用，否则会调用失败。Notes: This line of code must be called before the instantiation of the QApplication object; otherwise, it will fail
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

# determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    working_dir = os.path.dirname(os.path.realpath(sys.executable))
elif __file__:
    working_dir = os.path.split(os.path.realpath(__file__))[0]

# 主窗口
class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        # 初始化拖动相关属性
        self.m_drag = False
        self.m_DragPosition = QPoint()
        # 初始化动画属性
        self.animation = None
    
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
        if hasattr(self, 'mainFrame'):
            self.mainFrame.setGraphicsEffect(effect)

    def doFadeIn(self):
        # 动画
        # 如果动画不存在，创建一个新的
        if self.animation is None:
            self.animation = QPropertyAnimation(self, b'windowOpacity')
        # 持续时间250ms
        self.animation.setDuration(250)
        try:
            # 尝试先取消动画完成后关闭窗口的信号
            self.animation.finished.disconnect(self.close)
        except:
            pass
        # 停止当前动画
        self.animation.stop()
        # 透明度范围从0逐渐增加到1
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.start()

    def doFadeOut(self):
        # 如果动画不存在，创建一个新的
        if self.animation is None:
            self.animation = QPropertyAnimation(self, b'windowOpacity')
        # 停止当前动画
        self.animation.stop()
        # 动画完成则关闭窗口
        self.animation.finished.connect(self.close)
        # 透明度范围从1逐渐减少到0s
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.start()

    def setWarninginfo(self, text):
        # 检查是否有lab_info属性，避免在子类中调用时出错
        if hasattr(self, 'lab_info'):
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
            self.lab_info.setWordWrap(True)  # 启用自动换行
            self.lab_info.setText(text)

    def setSuccessinfo(self, text):
        # 检查是否有lab_info属性，避免在子类中调用时出错
        if hasattr(self, 'lab_info'):
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
            self.lab_info.setWordWrap(True)  # 启用自动换行
            self.lab_info.setText(text)

class ConfigWindow(Window):
    config = {}
    usage_data = []

    def _connect(self):
        self.btn_close.clicked.connect(self.save_config)

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
                        "is_clean": True,
                        "clean_pic_cache": True,
                        "clean_file": True,
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
        # 重新扫描微信目录，获取最新的用户列表
        self.selectVersion = selectVersion()
        new_data_dirs, new_user_names = self.selectVersion.getAllPath()
        
        # 读取现有配置
        with open(working_dir + "/config.json", encoding="utf-8") as fd:
            self.config = json.load(fd)
        
        # 如果扫描到了新的用户目录，更新配置
        if new_data_dirs:
            # 创建现有用户配置的映射，用于保留已有配置
            existing_user_map = {user["wechat_id"].lower(): user for user in self.config["users"]}
            
            # 更新data_dir为最新扫描到的目录
            self.config["data_dir"] = new_data_dirs
            
            # 更新users列表，保留已有配置，添加新用户
            updated_users = []
            for user_name in new_user_names:
                user_lower = user_name.lower()
                if user_lower in existing_user_map:
                    # 保留已有配置，但更新wechat_id为正确的大小写
                    user_config = existing_user_map[user_lower].copy()
                    user_config["wechat_id"] = user_name
                    updated_users.append(user_config)
                else:
                    # 新用户，使用默认配置
                    updated_users.append({
                        "wechat_id": user_name,
                        "clean_days": "365",
                        "is_clean": True,
                        "clean_pic_cache": True,
                        "clean_file": True,
                        "clean_pic": True,
                        "clean_video": True,
                        "is_timer": True,
                        "timer": "0h"
                    })
            
            # 更新配置
            self.config["users"] = updated_users
            
            # 保存更新后的配置
            with open(working_dir + "/config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        
        # 初始化表格
        self.init_table()
        
        self.setSuccessinfo("请确认每个账号的删除内容及时间，以防误删！")

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
                    "clean_file": True,
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

    def init_table(self):
        """初始化表格"""
        # 确保mainFrame有一个有效的布局
        if not self.mainFrame.layout():
            main_layout = QVBoxLayout(self.mainFrame)
            main_layout.setContentsMargins(10, 10, 10, 10)
            main_layout.setSpacing(10)
            # 添加信息标签到布局
            main_layout.addWidget(self.lab_info)
        else:
            # 清空mainFrame布局中的所有控件，但保留lab_info
            main_layout = self.mainFrame.layout()
            # 先移除所有控件
            for i in reversed(range(main_layout.count())):
                item = main_layout.itemAt(i)
                if item.widget() and item.widget() != self.lab_info:
                    item.widget().deleteLater()
                main_layout.removeItem(item)
            # 重新添加lab_info到布局
            main_layout.addWidget(self.lab_info)
        
        # 创建表格，调整列数和列名（共8列）
        self.table = QTableWidget(0, 8)  # 微信id、所在盘符、占用空间、清理图片、清理文件、清理视频、清理缓存、保留天数
        self.table.setHorizontalHeaderLabels(["微信ID", "所在盘符", "占用空间", "清理图片", "清理文件", "清理视频", "清理缓存", "保留天数"])
        
        # 设置表格属性，调整列宽以适应窗口宽度，避免横向滚动条
        self.table.setColumnWidth(0, 140)  # 微信ID
        self.table.setColumnWidth(1, 90)   # 所在盘符
        self.table.setColumnWidth(2, 100)  # 占用空间
        self.table.setColumnWidth(3, 90)   # 清理图片
        self.table.setColumnWidth(4, 90)   # 清理文件
        self.table.setColumnWidth(5, 90)   # 清理视频
        self.table.setColumnWidth(6, 90)   # 清理缓存
        self.table.setColumnWidth(7, 90)   # 保留天数
        self.table.horizontalHeader().setStretchLastSection(False)
        
        # 设置表格为固定宽度，不允许横向滚动
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 设置表格默认对齐方式为居中
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        
        # 设置表格样式，使复选框居中
        self.table.setStyleSheet("""
            QTableWidget::indicator {
                subcontrol-origin: padding;
                subcontrol-position: center;
                margin: auto;
            }
            QTableWidget QAbstractItemView::item {
                text-align: center;
                vertical-align: middle;
            }
        """)
        
        # 设置表格的大小策略，使其能够扩展
        self.table.setSizePolicy(self.table.sizePolicy().Expanding, self.table.sizePolicy().Expanding)
        
        # 填充用户数据（仅微信ID，暂不扫描空间占用）
        self.fill_table_with_user_data()
        
        # 连接信号
        self.table.itemChanged.connect(self.on_item_changed)
        
        # 添加表格到布局
        main_layout.addWidget(self.table)
        
        # 添加按钮布局（扫描空间占用和关闭按钮）
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 创建扫描按钮
        self.btn_scan = QPushButton("扫描空间占用")
        self.btn_scan.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
                margin-right: 10px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        self.btn_scan.clicked.connect(self.scan_space_usage)
        button_layout.addWidget(self.btn_scan)
        
        # 添加关闭按钮
        button_layout.addWidget(self.btn_close)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

    def fill_table_with_user_data(self):
        """仅填充用户数据，不扫描空间占用"""
        # 清空表格
        self.table.setRowCount(0)
        
        # 填充用户数据
        for i, user_config in enumerate(self.config["users"]):
            user_name = user_config["wechat_id"]
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # 微信ID列
            id_item = QTableWidgetItem(user_name)
            id_item.setTextAlignment(Qt.AlignCenter)
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, id_item)
            
            # 所在盘符列（在扫描微信id时获取）
            # 从data_dir中获取所在盘符
            drive = ""
            if i < len(self.config["data_dir"]):
                user_dir = self.config["data_dir"][i]
                drive = os.path.splitdrive(user_dir)[0]
                if not drive:
                    drive = "本地磁盘"
            drive_item = QTableWidgetItem(drive)
            drive_item.setTextAlignment(Qt.AlignCenter)
            drive_item.setFlags(drive_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, drive_item)
            
            # 占用空间列（初始为空）
            size_item = QTableWidgetItem("")
            size_item.setTextAlignment(Qt.AlignCenter)
            size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, size_item)
            
            # 清理图片列（复选框）
            pic_widget = QWidget()
            pic_layout = QHBoxLayout(pic_widget)
            pic_layout.setContentsMargins(5, 2, 5, 2)
            pic_layout.setSpacing(5)
            
            pic_checkbox = QCheckBox()
            pic_checkbox.setChecked(user_config["clean_pic"])
            pic_checkbox.setProperty("row", row)
            pic_checkbox.setProperty("user_id", user_name)
            pic_checkbox.setProperty("type", "clean_pic")
            pic_checkbox.stateChanged.connect(lambda state, c=pic_checkbox: self.on_detail_checkbox_changed(c))
            
            pic_layout.addWidget(pic_checkbox, 0, Qt.AlignCenter)
            pic_widget.setLayout(pic_layout)
            self.table.setCellWidget(row, 3, pic_widget)
            
            # 清理文件列（复选框）
            file_widget = QWidget()
            file_layout = QHBoxLayout(file_widget)
            file_layout.setContentsMargins(5, 2, 5, 2)
            file_layout.setSpacing(5)
            
            file_checkbox = QCheckBox()
            file_checkbox.setChecked(user_config["clean_file"])
            file_checkbox.setProperty("row", row)
            file_checkbox.setProperty("user_id", user_name)
            file_checkbox.setProperty("type", "clean_file")
            file_checkbox.stateChanged.connect(lambda state, c=file_checkbox: self.on_detail_checkbox_changed(c))
            
            file_layout.addWidget(file_checkbox, 0, Qt.AlignCenter)
            file_widget.setLayout(file_layout)
            self.table.setCellWidget(row, 4, file_widget)
            
            # 清理视频列（复选框）
            video_widget = QWidget()
            video_layout = QHBoxLayout(video_widget)
            video_layout.setContentsMargins(5, 2, 5, 2)
            video_layout.setSpacing(5)
            
            video_checkbox = QCheckBox()
            video_checkbox.setChecked(user_config["clean_video"])
            video_checkbox.setProperty("row", row)
            video_checkbox.setProperty("user_id", user_name)
            video_checkbox.setProperty("type", "clean_video")
            video_checkbox.stateChanged.connect(lambda state, c=video_checkbox: self.on_detail_checkbox_changed(c))
            
            video_layout.addWidget(video_checkbox, 0, Qt.AlignCenter)
            video_widget.setLayout(video_layout)
            self.table.setCellWidget(row, 5, video_widget)
            
            # 清理缓存列（复选框）
            cache_widget = QWidget()
            cache_layout = QHBoxLayout(cache_widget)
            cache_layout.setContentsMargins(5, 2, 5, 2)
            cache_layout.setSpacing(5)
            
            cache_checkbox = QCheckBox()
            cache_checkbox.setChecked(user_config["clean_pic_cache"])
            cache_checkbox.setProperty("row", row)
            cache_checkbox.setProperty("user_id", user_name)
            cache_checkbox.setProperty("type", "clean_pic_cache")
            cache_checkbox.stateChanged.connect(lambda state, c=cache_checkbox: self.on_detail_checkbox_changed(c))
            
            cache_layout.addWidget(cache_checkbox, 0, Qt.AlignCenter)
            cache_widget.setLayout(cache_layout)
            self.table.setCellWidget(row, 6, cache_widget)
            
            # 保留天数列
            clean_days = QTableWidgetItem()
            clean_days.setText(str(user_config["clean_days"]))
            clean_days.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 7, clean_days)

    def scan_space_usage(self):
        """扫描空间占用"""
        self.setSuccessinfo("正在扫描空间占用...")
        
        # 创建扫描线程
        self.scan_thread = SpaceScanThread(self.config)
        self.scan_thread.scan_progress_signal.connect(self.update_progress)
        self.scan_thread.scan_complete_signal.connect(self.update_space_usage)
        
        # 启动线程
        self.scan_thread.start()

    def update_progress(self, progress):
        """更新进度信息"""
        self.setSuccessinfo(f"正在扫描空间占用... {progress}%")

    def update_space_usage(self, usage_data):
        """更新空间占用数据到表格"""
        self.usage_data = usage_data
        
        # 更新表格数据
        for data in usage_data:
            # 跳过总占用行
            if data["id"] == "total":
                continue
            
            # 查找对应的用户行
            for row in range(self.table.rowCount()):
                id_item = self.table.item(row, 0)  # 微信ID列
                if id_item and id_item.text() == data["name"]:
                    # 更新占用空间
                    size_item = self.table.item(row, 2)  # 占用空间列
                    if size_item:
                        size_item.setText(data["size"])
                    break
        
        # 按占用空间从大到小排序表格
        self.sort_table_by_size()
        
        self.setSuccessinfo("空间占用扫描完成！")
    
    def sort_table_by_size(self):
        """按占用空间从大到小排序表格"""
        # 自定义排序函数，将大小字符串转换为字节数
        def size_to_bytes(size_str):
            if not size_str:
                return 0
            size_str = size_str.strip()
            try:
                # 提取数值和单位
                if "GB" in size_str:
                    # 提取GB前的数值部分
                    value_str = size_str.split("GB")[0].strip()
                    return float(value_str) * 1024 * 1024 * 1024
                elif "MB" in size_str:
                    # 提取MB前的数值部分
                    value_str = size_str.split("MB")[0].strip()
                    return float(value_str) * 1024 * 1024
                elif "KB" in size_str:
                    # 提取KB前的数值部分
                    value_str = size_str.split("KB")[0].strip()
                    return float(value_str) * 1024
                elif "B" in size_str:
                    # 提取B前的数值部分
                    value_str = size_str.split("B")[0].strip()
                    return float(value_str)
                else:
                    return 0
            except (ValueError, IndexError):
                return 0
        
        # 获取所有行数据
        row_data = []
        for row in range(self.table.rowCount()):
            # 获取行数据
            id_item = self.table.item(row, 0)
            drive_item = self.table.item(row, 1)
            size_item = self.table.item(row, 2)
            days_item = self.table.item(row, 7)
            
            # 保存复选框状态
            checkbox_states = {}
            for col in [3, 4, 5, 6]:  # 复选框列
                widget = self.table.cellWidget(row, col)
                if widget:
                    # 获取复选框状态
                    checkbox = widget.findChild(QCheckBox)
                    if checkbox:
                        checkbox_states[col] = checkbox.isChecked()
                    else:
                        checkbox_states[col] = False
                else:
                    checkbox_states[col] = False
            
            # 收集行数据
            row_info = {
                'id': id_item.text() if id_item else '',
                'drive': drive_item.text() if drive_item else '',
                'size_str': size_item.text() if size_item else '',
                'size_bytes': size_to_bytes(size_item.text() if size_item else ''),
                'days': days_item.text() if days_item else '',
                'checkbox_states': checkbox_states
            }
            row_data.append(row_info)
        
        # 按大小从大到小排序
        row_data.sort(key=lambda x: x['size_bytes'], reverse=True)
        
        # 清空表格并重新添加行
        self.table.setRowCount(0)
        for data in row_data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # 微信ID列
            id_item = QTableWidgetItem(data['id'])
            id_item.setTextAlignment(Qt.AlignCenter)
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, id_item)
            
            # 所在盘符列
            drive_item = QTableWidgetItem(data['drive'])
            drive_item.setTextAlignment(Qt.AlignCenter)
            drive_item.setFlags(drive_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, drive_item)
            
            # 占用空间列
            size_item = QTableWidgetItem(data['size_str'])
            size_item.setTextAlignment(Qt.AlignCenter)
            size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, size_item)
            
            # 清理图片列（复选框）
            pic_widget = QWidget()
            pic_layout = QHBoxLayout(pic_widget)
            pic_layout.setContentsMargins(5, 2, 5, 2)
            pic_layout.setSpacing(5)
            
            pic_checkbox = QCheckBox()
            pic_checkbox.setChecked(data['checkbox_states'].get(3, False))
            pic_checkbox.setProperty("row", row)
            pic_checkbox.setProperty("user_id", data['id'])
            pic_checkbox.setProperty("type", "clean_pic")
            pic_checkbox.stateChanged.connect(lambda state, c=pic_checkbox: self.on_detail_checkbox_changed(c))
            
            pic_layout.addWidget(pic_checkbox, 0, Qt.AlignCenter)
            pic_widget.setLayout(pic_layout)
            self.table.setCellWidget(row, 3, pic_widget)
            
            # 清理文件列（复选框）
            file_widget = QWidget()
            file_layout = QHBoxLayout(file_widget)
            file_layout.setContentsMargins(5, 2, 5, 2)
            file_layout.setSpacing(5)
            
            file_checkbox = QCheckBox()
            file_checkbox.setChecked(data['checkbox_states'].get(4, False))
            file_checkbox.setProperty("row", row)
            file_checkbox.setProperty("user_id", data['id'])
            file_checkbox.setProperty("type", "clean_file")
            file_checkbox.stateChanged.connect(lambda state, c=file_checkbox: self.on_detail_checkbox_changed(c))
            
            file_layout.addWidget(file_checkbox, 0, Qt.AlignCenter)
            file_widget.setLayout(file_layout)
            self.table.setCellWidget(row, 4, file_widget)
            
            # 清理视频列（复选框）
            video_widget = QWidget()
            video_layout = QHBoxLayout(video_widget)
            video_layout.setContentsMargins(5, 2, 5, 2)
            video_layout.setSpacing(5)
            
            video_checkbox = QCheckBox()
            video_checkbox.setChecked(data['checkbox_states'].get(5, False))
            video_checkbox.setProperty("row", row)
            video_checkbox.setProperty("user_id", data['id'])
            video_checkbox.setProperty("type", "clean_video")
            video_checkbox.stateChanged.connect(lambda state, c=video_checkbox: self.on_detail_checkbox_changed(c))
            
            video_layout.addWidget(video_checkbox, 0, Qt.AlignCenter)
            video_widget.setLayout(video_layout)
            self.table.setCellWidget(row, 5, video_widget)
            
            # 清理缓存列（复选框）
            cache_widget = QWidget()
            cache_layout = QHBoxLayout(cache_widget)
            cache_layout.setContentsMargins(5, 2, 5, 2)
            cache_layout.setSpacing(5)
            
            cache_checkbox = QCheckBox()
            cache_checkbox.setChecked(data['checkbox_states'].get(6, False))
            cache_checkbox.setProperty("row", row)
            cache_checkbox.setProperty("user_id", data['id'])
            cache_checkbox.setProperty("type", "clean_pic_cache")
            cache_checkbox.stateChanged.connect(lambda state, c=cache_checkbox: self.on_detail_checkbox_changed(c))
            
            cache_layout.addWidget(cache_checkbox, 0, Qt.AlignCenter)
            cache_widget.setLayout(cache_layout)
            self.table.setCellWidget(row, 6, cache_widget)
            
            # 保留天数列
            days_item = QTableWidgetItem(data['days'])
            days_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 7, days_item)

    def on_detail_checkbox_changed(self, checkbox):
        """处理细项复选框状态变化，实时保存配置"""
        user_id = checkbox.property("user_id")
        check_type = checkbox.property("type")
        is_checked = checkbox.isChecked()
        
        # 查找该用户在配置中的索引
        user_index = -1
        for i, user in enumerate(self.config["users"]):
            if user["wechat_id"].lower() == user_id.lower():
                user_index = i
                break
        
        if user_index == -1:
            print(f"未找到用户 {user_id} 的配置")
            return
        
        # 更新细项配置
        if check_type in self.config["users"][user_index]:
            self.config["users"][user_index][check_type] = is_checked
            
        # 保存配置到文件
        self.save_config_file()

    def on_item_changed(self, item):
        """处理表格单元格变化，实时保存配置"""
        row = item.row()
        col = item.column()
        
        # 只处理保留天数列的变化
        if col != 7:
            return
        
        # 获取当前行的数据
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        
        user_id = name_item.text()
        
        # 查找该用户在配置中的索引
        user_index = -1
        for i, user in enumerate(self.config["users"]):
            if user["wechat_id"].lower() == user_id.lower():
                user_index = i
                break
        
        if user_index == -1:
            print(f"未找到用户 {user_id} 的配置")
            return
        
        # 更新保留天数配置
        try:
            days = int(item.text())
            if days < 0:
                days = 0
            self.config["users"][user_index]["clean_days"] = str(days)
        except ValueError:
            # 如果输入不是数字，恢复原来的值
            item.setText(self.config["users"][user_index]["clean_days"])
            return
        
        # 保存配置到文件
        self.save_config_file()

    def save_config_file(self):
        """保存配置文件"""
        try:
            with open(working_dir + "/config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败：{str(e)}")
            self.setWarninginfo(f"保存配置失败：{str(e)}")

    def __init__(self):
        super().__init__()
        
        # 禁用默认的UI设置，直接创建自定义UI
        # 不使用ui.setupUi(self)，避免布局冲突
        
        # 创建主Frame
        from PyQt5.QtWidgets import QFrame
        self.mainFrame = QFrame()
        self.mainFrame.setStyleSheet("""\
.QFrame {
    background: rgb(245, 245, 245);
    border-radius: 3px;
}
""")
        
        # 创建关闭按钮
        self.btn_close = QPushButton("关闭")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        
        # 创建信息标签
        self.lab_info = QLabel("请确认每个账号的删除内容及时间，以防误删！")
        self.lab_info.setStyleSheet("""
            QLabel {
                border:1px solid #b7eb8f;
                border-radius:3px;
                line-height: 140px;
                padding: 5px;
                color: #434343;
                background: #f6ffed;
            }
        """)
        self.lab_info.setWordWrap(True)
        
        # 设置mainFrame为QMainWindow的centralWidget
        self.setCentralWidget(self.mainFrame)
        
        # 创建主布局
        main_layout = QVBoxLayout(self.mainFrame)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 添加信息标签到布局
        main_layout.addWidget(self.lab_info)
        
        # 设置窗口大小
        self.setFixedSize(900, 600)

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
                except Exception as e:
                    self.setWarninginfo(f"清理失败，请检查配置文件后重试\n错误信息：{str(e)}")
                return True
            elif object == self.lab_config:
                cw = ConfigWindow()
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
            path_three = correct_path / 'cache'
            path_four = correct_path / 'new/cache/path'  # 添加第四个路径
            self.getPathFileNum(now, day, path_one, path_two, path_three, path_four, file_list=file_list, dir_list=dir_list)
        if fileCheck:
            path_one = correct_path / 'Files'
            path_two = correct_path / 'FileStorage/File'
            path_three = correct_path / 'msg/file'
            path_four = correct_path / 'FileStorage/MsgAttach'  # 添加第四个路径
            path_five = correct_path / 'FileStorage/Sns/cache'  
            self.getPathFileNum(now, day, path_one, path_two, path_three, path_four, path_five, file_list=file_list, dir_list=dir_list)
        if picCheck:
            path_one = correct_path / 'Image/Image'
            path_two = correct_path / 'FileStorage/Image'
            path_three = correct_path / 'msg/attach'
            path_four = correct_path / 'new/image/path'  # 添加第四个路径
            self.getPathFileNum(now, day, path_one, path_two, path_three, path_four, file_list=file_list, dir_list=dir_list)
        if videoCheck:
            path_one = correct_path / 'Video'
            path_two = correct_path / 'FileStorage/Video'
            path_three = correct_path / 'msg/video'
            path_four = correct_path / 'new/video/path'  # 添加第四个路径
            self.getPathFileNum(now, day, path_one, path_two, path_three, path_four, file_list=file_list, dir_list=dir_list)

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

    def getPathFileNum(self, now, day, *paths, file_list, dir_list):
        # 递归搜索所有YYYY-MM格式目录的辅助函数
        def recursive_search_yyyymm_dirs(search_path):
            if not os.path.exists(search_path):
                return []
            
            result = []
            for root, dirs, files in os.walk(search_path):
                for dir_name in dirs:
                    if re.match('\d{4}(\-)\d{2}', dir_name) != None:
                        result.append(os.path.join(root, dir_name))
            return result
        
        td = datetime.datetime.now() - datetime.timedelta(days=day)
        td_year = td.year
        td_month = td.month
        
        # 遍历所有路径
        for i, current_path in enumerate(paths):
            if current_path and os.path.exists(current_path):
                # 第一个路径特殊处理（保持原有逻辑，直接处理文件）
                if i == 0:
                    self.pathFileDeal(now, day, current_path, file_list, dir_list)
                else:
                    # 其他路径处理YYYY-MM格式目录
                    # 递归搜索所有YYYY-MM格式目录
                    yyyymm_dirs = recursive_search_yyyymm_dirs(current_path)
                    
                    for dir_path in yyyymm_dirs:
                        # 提取目录名（YYYY-MM格式）
                        dir_name = os.path.basename(dir_path)
                        cyear = int(dir_name.split('-', 1)[0])
                        cmonth = int(dir_name.split('-', 1)[1])
                        
                        if self.__before_deadline(cyear, cmonth, td_year, td_month):
                            # 如果年月早于截止日期，直接添加整个目录到删除列表
                            dir_list.append(dir_path)
                        else:
                            if cmonth == td_month:
                                # 否则，只处理该目录下的文件
                                self.pathFileDeal(now, day, dir_path, file_list, dir_list)
                    
                    # 额外处理当前路径下的非YYYY-MM格式目录中的文件
                    # 只处理直接子目录，不递归
                    for item in os.listdir(current_path):
                        item_path = os.path.join(current_path, item)
                        if os.path.isdir(item_path) and not re.match('\d{4}(\-)\d{2}', item):
                            self.pathFileDeal(now, day, item_path, file_list, dir_list)

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
        try:
            # 检查配置文件是否存在
            config_path = os.path.join(working_dir, "config.json")
            if not os.path.exists(config_path):
                self.setWarninginfo("配置文件不存在，请先配置微信路径")
                return
            
            # 读取配置文件
            with open(config_path, encoding="utf-8") as fd:
                self.config = json.load(fd)
            
            # 检查配置文件格式是否正确
            if "users" not in self.config or "data_dir" not in self.config:
                self.setWarninginfo("配置文件格式错误，请重新配置")
                return
            
            i = 0
            need_clean = False
            self.thread_list.clear()  # 清空之前的线程列表
            total_file = 0
            total_dir = 0
            share_thread_arr = [0]
            
            # 遍历所有用户
            for value in self.config["users"]:
                file_list = []
                dir_list = []
                
                # 检查数据目录索引是否有效
                if i >= len(self.config["data_dir"]):
                    self.setWarninginfo(f"配置文件错误：第{i+1}个用户没有对应的路径")
                    return
                
                if value["is_clean"]:
                    # 调用get_fileNum函数收集需要清理的文件和目录
                    self.get_fileNum(self.config["data_dir"][i],
                                     int(value["clean_days"]),
                                     value["clean_pic_cache"], value["clean_file"],
                                     value["clean_pic"], value["clean_video"],
                                     file_list, dir_list)

                if len(file_list) + len(dir_list) != 0:
                    need_clean = True
                    total_file += len(file_list)
                    total_dir += len(dir_list)
                    thread = multiDeleteThread(file_list, dir_list, share_thread_arr)
                    thread.delete_process_signal.connect(self.callback)
                    # 连接线程完成信号，防止线程泄漏
                    thread.delete_complete_signal.connect(lambda: None)  # 空槽函数，确保信号被处理
                    self.thread_list.append(thread)
                i = i + 1

            if not need_clean:
                self.setWarninginfo("没有需要清理的文件")
            else:
                # 先设置总文件数和目录数，确保进度更新正确
                self.total_file = total_file
                self.total_dir = total_dir
                
                # 检查是否有需要清理的文件
                if total_file + total_dir == 0:
                    self.setWarninginfo("没有需要清理的文件")
                else:
                    # 显示清理开始信息
                    self.setSuccessinfo("正在清理中...")
                    # 启动清理线程
                    for thread in self.thread_list:
                        thread.start()  # 使用start()启动线程，而不是run()
                        # 设置线程完成后自动删除，防止内存泄漏
                        thread.finished.connect(thread.deleteLater)
        except Exception as e:
            # 捕获所有异常并显示详细错误信息
            import traceback
            error_msg = f"清理失败：{str(e)}\n{traceback.format_exc()}"
            print(error_msg)  # 打印到控制台便于调试
            self.setWarninginfo(f"清理失败：{str(e)}")

    def show_config_window(self):
        self.config_window = ConfigWindow()
        self.setSuccessinfo("已经准备好，可以开始了！")

    def __init__(self):
        super().__init__()
        
        # 使用转换后的UI代码
        self.ui = MainWindowUI()
        self.ui.setupUi(self)
        
        # 将UI控件引用添加到当前实例，以便直接访问
        self.lab_close = self.ui.lab_close
        self.lab_clean = self.ui.lab_clean
        self.lab_config = self.ui.lab_config
        self.lab_info = self.ui.lab_info
        self.bar_progress = self.ui.bar_progress
        self.mainFrame = self.ui.mainFrame
        self.lab_logo = self.ui.lab_logo
        self.lab_about = self.ui.lab_about
        
        # 初始化线程列表，用于存储清理线程，防止线程被提前销毁
        self.thread_list = []

        self._frame()
        self._eventfilter()
        self.doFadeIn()
        self.config_exists = True
        self.show()

        # 判断配置文件是否存在
        if not os.path.exists(working_dir + "/config.json"):
            self.setWarninginfo("首次使用，即将自动弹出配置窗口")
            self.config_exists = False

            timer = QTimer(self)
            timer.timeout.connect(self.show_config_window)
            timer.setSingleShot(True)  # 只执行一次
            
            # 设置定时器的时间间隔，这里设置为 1000ms（1秒）
            timer.start(1000)

# 用于显示空间占用结果的窗口类
class SpaceUsageWindow(QWidget):
    def __init__(self, usage_data):
        super().__init__()
        
        # 设置窗口属性
        self.setWindowTitle("微信空间占用")
        self.setGeometry(100, 100, 700, 400)  # 恢复原来的宽度
        self.setStyleSheet("* {font: 9pt '微软雅黑';}")
        
        # 读取配置文件
        self.config_path = os.path.join(working_dir, "config.json")
        with open(self.config_path, encoding="utf-8") as fd:
            self.config = json.load(fd)
        
        # 创建主布局
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # 创建表格，调整列数和列名
        self.table = QTableWidget(len(usage_data), 5)
        self.table.setHorizontalHeaderLabels(["微信名称", "所在盘符", "占用空间", "是否清理", "保留天数"])
        
        # 设置表格属性
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 100)
        self.table.horizontalHeader().setStretchLastSection(False)
        
        # 设置表格默认对齐方式为居中
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        
        # 设置表格样式，使复选框居中
        self.table.setStyleSheet("""
            QTableWidget::indicator {
                subcontrol-origin: padding;
                subcontrol-position: center;
                margin: auto;
            }
            QTableWidget QAbstractItemView::item {
                text-align: center;
                vertical-align: middle;
            }
        """)
        
        # 填充数据
        for row, data in enumerate(usage_data):
            name_item = QTableWidgetItem(data["name"])
            drive_item = QTableWidgetItem(data["drive"])
            size_item = QTableWidgetItem(data["size"])
            
            # 设置单元格对齐方式
            name_item.setTextAlignment(Qt.AlignCenter)
            drive_item.setTextAlignment(Qt.AlignCenter)
            size_item.setTextAlignment(Qt.AlignCenter)
            
            # 设置只读列（微信名称、所在盘符、占用空间）
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            drive_item.setFlags(drive_item.flags() & ~Qt.ItemIsEditable)
            size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
            
            # 添加到表格
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, drive_item)
            self.table.setItem(row, 2, size_item)
            
            # 跳过总占用行，只处理用户行
            if data["id"] != "total":
                # 更可靠的用户配置匹配：遍历所有data_dir路径，通过路径匹配用户
                user_config = None
                user_id = data["id"]
                
                # 首先尝试直接匹配wechat_id
                user_config = next((user for user in self.config["users"] if user["wechat_id"].lower() == user_id.lower()), None)
                
                # 如果直接匹配失败，尝试通过路径匹配
                if not user_config:
                    for i, user_dir in enumerate(self.config["data_dir"]):
                        dir_name = os.path.basename(user_dir)
                        if dir_name.lower() == user_id.lower() and i < len(self.config["users"]):
                            user_config = self.config["users"][i]
                            break
                
                # 如果还是没有匹配到，创建默认配置
                if not user_config:
                    # 查找是否有对应的用户配置
                    user_config = {
                        "wechat_id": user_id,
                        "clean_days": "365",
                        "is_clean": True,
                        "clean_pic_cache": True,
                        "clean_file": True,
                        "clean_pic": True,
                        "clean_video": True,
                        "is_timer": True,
                        "timer": "0h"
                    }
                
                # 是否清理列（复选框+文字）
                # 创建包含复选框和文字的自定义单元格
                check_widget = QWidget()
                check_layout = QHBoxLayout(check_widget)
                check_layout.setContentsMargins(5, 2, 5, 2)
                check_layout.setSpacing(5)
                
                # 创建复选框
                checkbox = QCheckBox()
                checkbox.setChecked(user_config["is_clean"])
                
                # 创建文字标签
                label = QLabel("清理")
                label.setAlignment(Qt.AlignCenter)
                
                # 将复选框和文字添加到布局
                check_layout.addWidget(checkbox, 0, Qt.AlignRight)
                check_layout.addWidget(label, 0, Qt.AlignLeft)
                check_layout.addStretch()
                
                # 存储行号和用户ID，以便信号处理
                checkbox.setProperty("row", row)
                checkbox.setProperty("user_id", user_id)
                checkbox.stateChanged.connect(lambda state, c=checkbox: self.on_checkbox_changed(c))
                
                # 设置单元格小部件
                self.table.setCellWidget(row, 3, check_widget)
                
                # 保留天数列（文本框）
                clean_days = QTableWidgetItem()
                clean_days.setText(str(user_config["clean_days"]))
                clean_days.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 4, clean_days)
            else:
                # 总占用行的编辑列设置为不可编辑
                for col in [3, 4]:
                    empty_item = QTableWidgetItem("")
                    empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row, col, empty_item)
        
        # 连接单元格变化信号，实现实时保存
        self.table.itemChanged.connect(self.on_item_changed)
        
        # 添加表格到布局
        main_layout.addWidget(self.table)
        
        # 创建关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        
        # 添加按钮到布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)
        
        # 显示窗口
        self.show()
    
    def on_checkbox_changed(self, checkbox):
        """处理复选框状态变化，实时保存配置"""
        # 获取复选框关联的用户ID
        user_id = checkbox.property("user_id")
        if not user_id:
            return
        
        # 查找该用户在配置中的索引
        user_index = -1
        for i, user in enumerate(self.config["users"]):
            if user["wechat_id"].lower() == user_id.lower():
                user_index = i
                break
        
        if user_index == -1:
            print(f"未找到用户 {user_id} 的配置")
            return
        
        # 更新是否清理配置
        self.config["users"][user_index]["is_clean"] = checkbox.isChecked()
        
        # 保存配置到文件
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print(f"用户 {user_id} 的配置已保存")
        except Exception as e:
            print(f"保存配置失败：{str(e)}")
    
    def on_item_changed(self, item):
        """处理表格单元格变化，实时保存配置"""
        row = item.row()
        col = item.column()
        
        # 获取当前行的数据
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        
        user_id = name_item.text()
        
        # 跳过总占用行
        if user_id == "微信总占用":
            return
        
        # 只处理保留天数列的变化
        if col != 4:
            return
        
        # 查找该用户在配置中的索引，使用与初始化相同的匹配逻辑
        user_index = -1
        
        # 首先尝试直接匹配wechat_id
        for i, user in enumerate(self.config["users"]):
            if user["wechat_id"].lower() == user_id.lower():
                user_index = i
                break
        
        if user_index == -1:
            print(f"未找到用户 {user_id} 的配置")
            return
        
        # 更新保留天数配置
        try:
            days = int(item.text())
            if days < 0:
                days = 0
            self.config["users"][user_index]["clean_days"] = str(days)
        except ValueError:
            # 如果输入不是数字，恢复原来的值
            item.setText(self.config["users"][user_index]["clean_days"])
            return
        
        # 保存配置到文件
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print(f"用户 {user_id} 的配置已保存")
        except Exception as e:
            print(f"保存配置失败：{str(e)}")

# 用于扫描空间占用的线程类
class SpaceScanThread(QThread):
    scan_progress_signal = pyqtSignal(int)
    scan_complete_signal = pyqtSignal(list)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        
    def get_dir_size(self, path):
        """计算目录大小"""
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += self.get_dir_size(entry.path)
        except Exception as e:
            print(f"计算目录大小失败：{str(e)}")
        return total
    
    def format_size(self, size_bytes):
        """格式化字节大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    def run(self):
        """扫描空间占用"""
        usage_data = []
        grand_total_size = 0
        
        # 1. 使用selectVersion类的getAllPath方法获取微信主目录和用户列表
        sv = selectVersion()
        user_dirs, user_names = sv.getAllPath()
        
        # 2. 如果没有找到用户目录，使用配置文件中的目录
        if not user_dirs and "data_dir" in self.config and len(self.config["data_dir"]) > 0:
            user_dirs = self.config["data_dir"]
            user_names = [user["wechat_id"] for user in self.config["users"]]
        
        # 3. 计算总目录数用于进度显示
        total_dirs = len(user_dirs)
        if total_dirs == 0:
            # 没有目录需要扫描，发送0%进度后返回
            self.scan_progress_signal.emit(0)
            self.scan_complete_signal.emit(usage_data)
            return
        
        # 4. 遍历所有用户目录
        for i, (user_dir, user_name) in enumerate(zip(user_dirs, user_names)):
            if os.path.exists(user_dir):
                # 直接计算整个用户目录的大小，包括所有子目录
                user_size = self.get_dir_size(user_dir)
                grand_total_size += user_size
                
                # 获取所在盘符
                drive = os.path.splitdrive(user_dir)[0]
                if not drive:
                    drive = "本地磁盘"
                
                # 保存用户结果，包括盘符信息
                size_str = self.format_size(user_size)
                usage_data.append({
                    "name": user_name,
                    "id": user_name,
                    "drive": drive,
                    "size": size_str
                })
            
            # 发送进度信号
            progress = int((i + 1) / total_dirs * 100)
            self.scan_progress_signal.emit(progress)
        
        # 5. 按占用空间从大到小排序（跳过总占用行）
        def size_key(item):
            # 将格式化的大小字符串转换为字节数用于排序
            size_str = item["size"]
            if size_str.endswith(" GB"):
                return float(size_str[:-3]) * 1024 * 1024 * 1024
            elif size_str.endswith(" MB"):
                return float(size_str[:-3]) * 1024 * 1024
            elif size_str.endswith(" KB"):
                return float(size_str[:-3]) * 1024
            else:
                return float(size_str[:-2])
        
        # 排序用户数据（排除总占用行）
        usage_data.sort(key=size_key, reverse=True)
        
        # 6. 添加总占用信息，总占用的盘符显示为"总计"
        if grand_total_size > 0:
            total_size_str = self.format_size(grand_total_size)
            usage_data.insert(0, {
                "name": "微信总占用",
                "id": "total",
                "drive": "总计",
                "size": total_size_str
            })
        
        # 7. 确保进度条停留在100%
        self.scan_progress_signal.emit(100)
        
        # 8. 发送扫描完成信号
        self.scan_complete_signal.emit(usage_data)

if __name__ == '__main__':
    app = QApplication([])
    win = MainWindow()
    app.exec_()
