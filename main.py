import sys

from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog, QGraphicsDropShadowEffect, QListWidgetItem, QListView, \
    QWidget, QLabel, QFrame, QHBoxLayout, QVBoxLayout, QGridLayout, QFileDialog, QMessageBox, QTableWidget, \
    QTableWidgetItem, QHeaderView, QPushButton, QAbstractItemView
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal, QMutex, QSize, QEvent, QPoint, QTimer
from PyQt5.QtGui import QMouseEvent, QCursor, QColor
from PyQt5.uic import loadUi

from pathlib import Path
from dateutil import relativedelta
import utils.resources
import os, datetime, time, re, math, shutil, json, logging

from utils.deleteThread import *
from utils.multiDeleteThread import multiDeleteThread
from utils.selectVersion import *
from utils.selectVersion import check_dir, existing_user_config, find_all_wechat_paths, get_dir_name, is_wechat_like_account_dir
from utils.scanThread import ScanThread
# 设置应用程序在高DPI屏幕上启用高DPI缩放。Set the application to enable high DPI scaling on high DPI screens
# 注意事项：此行代码必须在QApplication实例化之前调用，否则会调用失败。Notes: This line of code must be called before the instantiation of the QApplication object; otherwise, it will fail
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

# determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    working_dir = os.path.dirname(os.path.realpath(sys.executable))
elif __file__:
    working_dir = os.path.split(os.path.realpath(__file__))[0]

# 统一配置、日志、白名单、自动清理状态文件的位置，避免不同模块各读各的。
CONFIG_PATH = os.path.join(working_dir, "config.json")
LOG_PATH = os.path.join(working_dir, "cleanmywechat.log")
STATE_PATH = os.path.join(working_dir, "clean_state.json")
WHITELIST_PATH = os.path.join(working_dir, "whitelist.txt")
PREVIEW_PATH = os.path.join(working_dir, "last_scan_preview.txt")

logging.basicConfig(
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8")],
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


# 按扩展名分组，后续扫描预览和白名单判断都用这一套规则。
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff', '.heic', '.dat'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v', '.3gp'}
DOCUMENT_EXTS = {'.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf', '.txt', '.csv'}
ARCHIVE_EXTS = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'}
CACHE_EXTS = {'.cache', '.tmp', '.temp', '.log', '.old'}
# 这些属于数据库或程序运行组件，任何清理模式下都直接跳过。
SAFE_SKIP_EXTS = {
    '.db', '.sqlite', '.sqlite3', '.db-shm', '.db-wal', '.ldb', '.sst',
    '.dll', '.exe', '.msi', '.sys', '.ocx', '.pyd', '.so', '.dylib',
    '.bat', '.cmd', '.ps1', '.vbs', '.js', '.jar', '.pak'
}

# 这些目录通常放运行组件或程序资源，不当成缓存目录递归。
PROTECTED_DIR_NAMES = {
    'bin', 'runtime', 'runtimes', 'plugin', 'plugins', 'xplugin', 'module', 'modules',
    'framework', 'frameworks', 'locales', 'resources', 'swiftshader', 'installer',
    'update', 'updates', 'crashpad', 'web_shell', 'multitab'
}

# 只把名字明确指向缓存、日志、临时文件的目录加入新版微信系统区清理范围。
SAFE_CACHE_DIR_NAMES = {
    'cache', 'code cache', 'gpucache', 'dawncache', 'shadercache', 'logs', 'log',
    'temp', 'tmp', 'blob_storage'
}

CATEGORY_NAME = {
    'cache': '缓存/日志',
    'image': '图片',
    'video': '视频',
    'file': '普通文件',
    'document': '文档',
    'archive': '压缩包',
    'other': '其他'
}


DEFAULT_GLOBAL_CONFIG = {
    # 定时清理默认关闭，用户确认后可以在 config.json 里打开，避免第一次运行就自动清理。
    "auto_clean_enable": False,
    "auto_clean_interval_days": 30,
    "auto_clean_confirm": True,
    "run_at_startup": False,
    "startup_clean_cache_only": False,
    "direct_delete": False
}

LEGACY_GLOBAL_CONFIG_KEYS = (
    "scan_system_cache",
    "scan_wechat4_cache",
    "scan_mini_program_cache",
    "scan_wxwork_cache",
)

DEFAULT_USER_EXTRA = {
    # 新增新版微信和企业微信常见目录，默认开启扫描，但仍受“保留天数”和“清理前确认”控制。
    "client_type": "wechat",
    "clean_msg_attach": True,
    "clean_system_cache": True,
    "clean_log_cache": True,
    "clean_web_cache": True,
    "clean_miniprogram_cache": True,
    "clean_wxwork_cache": True,
    # 白名单默认开启，重要办公文件默认不清理，降低误删风险。
    "use_whitelist": True,
    "whitelist_paths": [],
    "whitelist_exts": [
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf",
        ".dll", ".exe", ".msi", ".sys", ".ocx", ".pyd", ".pak"
    ],
    # 文件类型细分，用户可以在 config.json 中精确控制。
    "clean_ext_groups": {
        "image": True,
        "video": True,
        "document": True,
        "archive": True,
        "cache": True,
        "other": True
    }
}


def load_json(path, default_value):
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.exception("读取 JSON 失败：%s", path)
    return default_value


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def format_size(size):
    try:
        size = float(size)
    except Exception:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size = size / 1024
        index += 1
    if index == 0:
        return f"{int(size)} {units[index]}"
    return f"{size:.2f} {units[index]}"


def normalize_ext(ext):
    if not ext:
        return ""
    ext = ext.lower().strip()
    if ext and not ext.startswith('.'):
        ext = '.' + ext
    return ext


def ensure_whitelist_file():
    # 提供一个可直接编辑的白名单文件，不影响原有界面。
    if not os.path.exists(WHITELIST_PATH):
        with open(WHITELIST_PATH, "w", encoding="utf-8") as f:
            f.write("# 一行一个白名单路径或扩展名，示例：\n")
            f.write("# D:/重要文件\n")
            f.write("# .pdf\n")
            f.write("# .docx\n")


def read_whitelist_file():
    ensure_whitelist_file()
    paths = []
    exts = []
    try:
        with open(WHITELIST_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('.') or (not os.path.sep in line and len(line) <= 8):
                    exts.append(normalize_ext(line))
                else:
                    paths.append(os.path.abspath(os.path.expandvars(line)))
    except Exception:
        logging.exception("读取白名单失败")
    return paths, exts


def ensure_config_defaults(config):
    # 兼容旧 config.json，老配置不用手动删，启动后自动补齐新字段。
    if not isinstance(config, dict):
        config = {}
    config.setdefault("data_dir", [])
    config.setdefault("users", [])
    global_config = config.setdefault("global", {})
    for key, value in DEFAULT_GLOBAL_CONFIG.items():
        global_config.setdefault(key, value)
    for key in LEGACY_GLOBAL_CONFIG_KEYS:
        global_config.pop(key, None)

    for index, user in enumerate(config.get("users", [])):
        for key, value in DEFAULT_USER_EXTRA.items():
            if isinstance(value, dict):
                user.setdefault(key, {})
                for k2, v2 in value.items():
                    user[key].setdefault(k2, v2)
            elif isinstance(value, list):
                user.setdefault(key, list(value))
            else:
                user.setdefault(key, value)
        # 账号和目录直接绑定，保留旧 data_dir 列表只是为了兼容旧版本。
        if "data_dir" not in user and index < len(config.get("data_dir", [])):
            user["data_dir"] = config["data_dir"][index]
    valid_users = []
    valid_data_dirs = []
    for user in config.get("users", []):
        data_dir = user.get("data_dir")
        if data_dir and is_wechat_like_account_dir(data_dir):
            valid_users.append(user)
            valid_data_dirs.append(data_dir)
    config["users"] = valid_users
    config["data_dir"] = valid_data_dirs
    return config


def load_config_file():
    config = load_json(CONFIG_PATH, {"data_dir": [], "users": []})
    config = ensure_config_defaults(config)
    config = merge_detected_accounts(config)
    try:
        save_json(CONFIG_PATH, config)
    except Exception:
        logging.exception("写入配置默认值失败")
    return config


def merge_detected_accounts(config):
    try:
        known_dirs = {
            os.path.normcase(os.path.abspath(user.get("data_dir", "")))
            for user in config.get("users", [])
            if user.get("data_dir")
        }
        known_ids = {user.get("wechat_id") for user in config.get("users", [])}
        for root_path in find_all_wechat_paths():
            dir_list, user_list = get_dir_name(root_path)
            for index, wechat_id in enumerate(user_list):
                data_dir = dir_list[index]
                dir_key = os.path.normcase(os.path.abspath(data_dir))
                if dir_key in known_dirs or wechat_id in known_ids:
                    continue
                config["users"].append(make_default_user_config(wechat_id, data_dir))
                config["data_dir"].append(data_dir)
                known_dirs.add(dir_key)
                known_ids.add(wechat_id)
    except Exception:
        logging.exception("自动合并微信账号目录失败")
    return ensure_config_defaults(config)


def make_default_user_config(wechat_id, data_dir):
    user = {
        "wechat_id": wechat_id,
        "data_dir": data_dir,
        "client_type": detect_client_type(data_dir),
        "clean_days": "365",
        "is_clean": True,
        "clean_pic_cache": True,
        "clean_file": False,
        "clean_pic": True,
        "clean_video": True,
        "is_timer": True,
        "timer": "0h"
    }
    ensure_config_defaults({"users": [user], "data_dir": [data_dir], "global": {}})
    return user


def get_file_type(file_path, default_category="other"):
    ext = os.path.splitext(str(file_path))[1].lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in DOCUMENT_EXTS:
        return "document"
    if ext in ARCHIVE_EXTS:
        return "archive"
    if ext in CACHE_EXTS:
        return "cache"
    return default_category


def safe_file_size(path):
    try:
        return os.path.getsize(path)
    except Exception:
        logging.exception("读取文件大小失败：%s", path)
        return 0


def is_sub_path(path, root):
    try:
        path = os.path.abspath(path).lower()
        root = os.path.abspath(root).lower()
        return path == root or path.startswith(root + os.sep)
    except Exception:
        return False


def detect_client_type(path):
    path_lower = str(path or '').lower()
    if 'wxwork' in path_lower or 'wework' in path_lower:
        return 'wxwork'
    return 'wechat'


def is_safe_cache_dir_name(name):
    base_name = str(name).lower().strip()
    if base_name in SAFE_CACHE_DIR_NAMES:
        return True
    return 'cache' in base_name or base_name.endswith('log') or base_name.endswith('logs')


def is_protected_file_path(path):
    path_str = str(path)
    ext = normalize_ext(os.path.splitext(path_str)[1])
    if ext in SAFE_SKIP_EXTS:
        return True
    parts = [p.lower() for p in Path(path_str).parts]
    return any(p in PROTECTED_DIR_NAMES for p in parts)


def apply_startup_setting(config):
    # 支持开机启动。默认不打开；用户在 config.json 中把 run_at_startup 改成 true 后生效。
    if os.name != 'nt':
        return
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "CleanMyWechat"
        global_config = config.get("global", {})
        if getattr(sys, 'frozen', False):
            command = '"{}" --startup'.format(sys.executable)
        else:
            command = '"{}" "{}" --startup'.format(sys.executable, os.path.abspath(__file__))
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if global_config.get("run_at_startup", False):
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception:
        logging.exception("设置开机启动失败")


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
        except Exception:
            logging.exception("窗口拖动失败")

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
        except Exception:
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

    def center_on_screen(self):
        try:
            screen = QApplication.desktop().availableGeometry(self)
            self.move(screen.center() - self.rect().center())
        except Exception:
            pass

    def setWarninginfo(self, text):
        self.lab_info.setStyleSheet("""
            .QLabel {
                color: #614a22;
                background-color: #fff4df;
                border: 1px solid #f0d39a;
                border-radius: 14px;
                padding: 10px 18px;
                font-size: 14px;
                line-height: 150%;
            }
            """)
        self.lab_info.setWordWrap(True)  # 启用自动换行
        self.lab_info.setText(text)

    def setSuccessinfo(self, text):
        self.lab_info.setStyleSheet("""
            .QLabel {
                color: #395246;
                background-color: #e8f6ed;
                border: 1px solid #c8e8d2;
                border-radius: 14px;
                padding: 10px 18px;
                font-size: 14px;
                line-height: 150%;
            }
            """)
        self.lab_info.setWordWrap(True)  # 启用自动换行
        self.lab_info.setText(text)


class ConfigWindow(Window):
    Signal_OneParameter = pyqtSignal(int)

    config = {}

    def _connect(self):
        self.combo_user.currentIndexChanged.connect(self.refresh_ui)
        self.btn_close.clicked.connect(self.save_config)
        self.btn_file.clicked.connect(self.open_file)
        if hasattr(self, "btn_open_account"):
            self.btn_open_account.clicked.connect(self.open_current_account_dir)

    def simplify_config_ui(self):
        self.setMinimumSize(780, 960)
        self.btn_file.setText("重新选择目录")
        if hasattr(self, "btn_open_account"):
            self.btn_open_account.setText("打开文件夹")
        self.btn_close.setText("保存设置")
        self.check_is_clean.setText("启用这个账号的清理")
        self.check_picdown.setText("图片")
        self.check_files.setText("收到的文档")
        self.check_video.setText("视频")
        self.check_picscache.setText("图片缓存、小程序和公众号缓存")
        if hasattr(self, "check_direct_delete"):
            self.check_direct_delete.setText("直接删除，不移动到回收站")
        if hasattr(self, "check_run_at_startup"):
            self.check_run_at_startup.setText("开机自启动")
        if hasattr(self, "check_auto_clean"):
            self.check_auto_clean.setText("定期自动清理")

    def open_current_account_dir(self):
        self.config = load_config_file()
        current_user = self.combo_user.currentText()
        for value in self.config.get("users", []):
            if value.get("wechat_id") == current_user:
                data_dir = value.get("data_dir")
                if data_dir and os.path.isdir(data_dir):
                    try:
                        os.startfile(data_dir)
                    except OSError as e:
                        self.setWarninginfo(f"打开文件夹失败：{e}")
                        return
                    self.setSuccessinfo(f"已打开账号文件夹：{data_dir}")
                    return
                self.setWarninginfo("当前账号文件夹不存在，请重新选择目录。")
                return
        self.setWarninginfo("没有找到当前账号的文件夹路径。")

    def open_file(self):
        openfile_path = QFileDialog.getExistingDirectory(self, '选择微信数据目录', '')
        if not openfile_path or openfile_path == '':
            return False
        if check_dir(openfile_path) == 0:
            self.setSuccessinfo('读取路径成功！')
            dir_list, user_list = get_dir_name(openfile_path)
            # 如果已有用户配置，那么写入新的用户配置，否则默认写入新配置
            user_config = []
            existing_user_config_dic = existing_user_config()
            for index, user_wx_id in enumerate(user_list):
                user_dir = dir_list[index]
                if user_wx_id in existing_user_config_dic:
                    uc = existing_user_config_dic[user_wx_id]
                    uc["data_dir"] = user_dir
                    uc["client_type"] = detect_client_type(user_dir)
                    user_config.append(uc)
                else:
                    user_config.append(make_default_user_config(user_wx_id, user_dir))

            config = ensure_config_defaults({"data_dir": dir_list, "users": user_config})

            save_json(CONFIG_PATH, config)
            self.load_config()
        else:
            self.setWarninginfo('请选择正确的文件夹！\n微信一般选 WeChat Files，企业微信一般选 WXWork。')

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
        self.config = load_config_file()

        self._loading_config = True
        self.combo_user.blockSignals(True)
        self.combo_user.clear()
        for value in self.config["users"]:
            self.combo_user.addItem(value["wechat_id"])
        self.combo_user.blockSignals(False)

        if not self.config["users"]:
            self._loading_config = False
            self.setWarninginfo("没有检测到微信账号，请手动选择 WeChat Files 文件夹。")
            return

        self.apply_user_config_to_ui(self.config["users"][0])
        self.apply_global_config_to_ui(self.config.get("global", {}))
        self.current_account_id = self.config["users"][0]["wechat_id"]
        self._loading_config = False
        self.check_is_clean.setText("启用这个账号的清理")
        self.setSuccessinfo("推荐使用默认选项。文件会先进入回收站，清理前会再次确认。")

        self.simplify_config_ui()

    def apply_user_config_to_ui(self, user_config):
        self.line_gobackdays.setText(str(user_config.get("clean_days", 365)))
        self.check_is_clean.setChecked(user_config.get("is_clean", True))
        self.check_picdown.setChecked(user_config.get("clean_pic", True))
        self.check_files.setChecked(user_config.get("clean_file", False))
        self.check_video.setChecked(user_config.get("clean_video", True))
        self.check_picscache.setChecked(user_config.get("clean_pic_cache", True))

    def apply_global_config_to_ui(self, global_config):
        if hasattr(self, "check_direct_delete"):
            self.check_direct_delete.setChecked(global_config.get("direct_delete", False))
        if hasattr(self, "check_run_at_startup"):
            self.check_run_at_startup.setChecked(global_config.get("run_at_startup", False))
        if hasattr(self, "check_auto_clean"):
            self.check_auto_clean.setChecked(global_config.get("auto_clean_enable", False))
        if hasattr(self, "line_auto_days"):
            self.line_auto_days.setText(str(global_config.get("auto_clean_interval_days", 30)))

    def refresh_ui(self):
        if getattr(self, "_loading_config", False):
            return
        previous_account_id = getattr(self, "current_account_id", "")
        current_account_id = self.combo_user.currentText()
        if previous_account_id and previous_account_id != current_account_id:
            self.persist_current_config(previous_account_id)

        self.config = load_config_file()

        for value in self.config["users"]:
            if value["wechat_id"] == current_account_id:
                self.apply_user_config_to_ui(value)
                self.current_account_id = current_account_id
                return

    def persist_current_config(self, account_id=None, notify=False, emit_signal=False):
        if not len(self.config):
            return False
        self.config = ensure_config_defaults(self.config)
        global_config = self.config.setdefault("global", {})
        if hasattr(self, "check_direct_delete"):
            global_config["direct_delete"] = self.check_direct_delete.isChecked()
        if hasattr(self, "check_run_at_startup"):
            global_config["run_at_startup"] = self.check_run_at_startup.isChecked()
        if hasattr(self, "check_auto_clean"):
            global_config["auto_clean_enable"] = self.check_auto_clean.isChecked()
        if hasattr(self, "line_auto_days"):
            try:
                interval_days = int(self.line_auto_days.text())
                global_config["auto_clean_interval_days"] = str(max(interval_days, 1))
            except ValueError:
                global_config["auto_clean_interval_days"] = "30"
        target_account_id = account_id or self.combo_user.currentText()
        for value in self.config["users"]:
            if value["wechat_id"] == target_account_id:
                try:
                    days = int(self.line_gobackdays.text())
                    value["clean_days"] = str(max(days, 0))
                except ValueError:
                    value["clean_days"] = "0"
                value["is_clean"] = self.check_is_clean.isChecked()
                value["clean_pic"] = self.check_picdown.isChecked()
                value["clean_file"] = self.check_files.isChecked()
                value["clean_video"] = self.check_video.isChecked()
                value["clean_pic_cache"] = self.check_picscache.isChecked()
                value["clean_miniprogram_cache"] = value["clean_pic_cache"]
                value["clean_system_cache"] = value["clean_pic_cache"]
                value["clean_log_cache"] = value["clean_pic_cache"]
                value["clean_web_cache"] = value["clean_pic_cache"]
                value["clean_ext_groups"] = {
                    "image": value["clean_pic"],
                    "video": value["clean_video"],
                    "document": value["clean_file"],
                    "archive": value["clean_file"],
                    "cache": value["clean_pic_cache"],
                    "other": value["clean_file"]
                }
                save_json(CONFIG_PATH, self.config)
                apply_startup_setting(self.config)
                if notify:
                    self.setSuccessinfo("更新配置文件成功")
                if emit_signal:
                    self.Signal_OneParameter.emit(1)
                return True
        return False

    def create_config(self):
        if not os.path.exists(CONFIG_PATH):
            if not self.check_wechat_exists():
                self.setWarninginfo("默认位置没有微信，请自定义位置")
                return

            self.config = ensure_config_defaults({"data_dir": self.version_scan, "users": []})
            for index, value in enumerate(self.users_scan):
                data_dir = self.version_scan[index] if index < len(self.version_scan) else ""
                self.config["users"].append(make_default_user_config(value, data_dir))
            save_json(CONFIG_PATH, self.config)
            self.load_config()
            self.setSuccessinfo("请确认每个账号的删除内容及时间，以防误删！")
        else:
            self.setSuccessinfo("请确认每个账号的删除内容及时间，以防误删！")
            self.load_config()

    def update_config(self):
        self.persist_current_config(notify=True, emit_signal=True)

    def __init__(self):
        super().__init__()
        loadUi(working_dir + "/images/config.ui", self)

        self._frame()
        self._connect()
        self.simplify_config_ui()

        self.doFadeIn()
        self.create_config()

        self.show()
        QTimer.singleShot(0, self.center_on_screen)


class MainWindow(Window):

    def deal_emit_slot(self, set_status):
        if set_status and not self.config_exists:
            self.setSuccessinfo("已经准备好，可以开始了！")
            self.config_exists = True

    def keep_ui_responsive(self):
        self.scan_tick = getattr(self, "scan_tick", 0) + 1
        if self.scan_tick % 250 == 0:
            self.bar_progress.setRange(0, 0)
            QApplication.processEvents()

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
                    self.setSuccessinfo("正在扫描可清理文件...")
                    self.justdoit()
                except Exception as e:
                    logging.exception("清理失败")
                    self.setWarninginfo("清理失败：" + str(e) + "\n详情请查看 cleanmywechat.log")
                return True
            elif object == self.lab_config:
                cw = ConfigWindow()
                cw.Signal_OneParameter.connect(self.deal_emit_slot)
                return True
            elif hasattr(self, "lab_preview") and object == self.lab_preview:
                try:
                    self.start_preview()
                except Exception as e:
                    self.setWarninginfo(f"预览失败：{str(e)}")
                return True
            elif hasattr(self, "lab_execute_delete") and object == self.lab_execute_delete:
                try:
                    self.execute_delete()
                except Exception as e:
                    self.setWarninginfo(f"删除失败：{str(e)}")
                return True
        return False

    def _eventfilter(self):
        # 事件过滤
        self.lab_close.installEventFilter(self)
        self.lab_clean.installEventFilter(self)
        self.lab_config.installEventFilter(self)
        if hasattr(self, "lab_preview"):
            self.lab_preview.installEventFilter(self)
        if hasattr(self, "lab_execute_delete"):
            self.lab_execute_delete.installEventFilter(self)

    def simplify_home_ui(self):
        self.setMinimumSize(560, 620)
        self.centralwidget.setStyleSheet("""
            QWidget#centralwidget {
                background-color: #eef7f1;
            }
        """)
        self.mainFrame.setStyleSheet("""
            QFrame#mainFrame {
                background-color: #f8fbf7;
                border: 1px solid #dcebe1;
                border-radius: 18px;
            }
        """)
        self.lab_info.setMinimumHeight(72)
        self.lab_info.setText("扫描微信缓存、日志和旧文件，清理前会再次确认。")
        self.lab_info.setStyleSheet("""
            .QLabel {
                color: #395246;
                background-color: #e8f6ed;
                border: 1px solid #c8e8d2;
                border-radius: 14px;
                padding: 10px 18px;
                font-size: 14px;
                line-height: 150%;
            }
        """)
        self.lab_clean.setText("扫描并清理")
        self.lab_config.setText("设置")
        self.lab_close.setText("退出")
        self.lab_about.setText("Clean My Wechat · 简单、安全地释放微信占用空间")
        self.lab_about.setStyleSheet("""
            .QLabel {
                color: #6a7d72;
                font-size: 13px;
                padding: 8px 0 2px 0;
            }
        """)
        if hasattr(self, "lab_logo"):
            self.lab_logo.show()
            self.lab_logo.setMinimumSize(196, 196)
            self.lab_logo.setStyleSheet("""
                .QLabel {
                    image: url(:/icon/wechat.png);
                    background-color: #eaf8ee;
                    border: 1px solid #c9ecd3;
                    border-radius: 98px;
                    padding: 18px;
                }
            """)
        self.bar_progress.setMinimumHeight(26)
        self.bar_progress.setStyleSheet("""
            .QProgressBar {
                background-color: #e5efe8;
                border: 1px solid #d1e2d6;
                border-radius: 13px;
                color: #395246;
                font-size: 12px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2fbf68;
                border-radius: 12px;
            }
        """)
        self.lab_clean.setMinimumHeight(48)
        self.lab_clean.setStyleSheet("""
            .QLabel {
                color: #f8fbf7;
                background-color: #16a85a;
                border: 1px solid #149550;
                border-radius: 24px;
                font-size: 16px;
                font-weight: 600;
                padding: 0 34px;
            }
            .QLabel:hover {
                background-color: #20b966;
                border: 1px solid #18a75a;
            }
        """)
        secondary_style = """
            .QLabel {
                color: #486256;
                background-color: #f1f7f3;
                border: 1px solid #d3e4d8;
                border-radius: 18px;
                font-size: 14px;
                padding: 0 16px;
            }
            .QLabel:hover {
                color: #159452;
                background-color: #e8f6ed;
                border: 1px solid #b9dfc5;
            }
        """
        self.lab_config.setStyleSheet(secondary_style)
        self.lab_close.setStyleSheet(secondary_style)
        for widget_name in ("check_select_all", "table_files", "lab_preview", "lab_execute_delete"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.hide()

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
        if not os.path.exists(CONFIG_PATH):
            self.setWarninginfo("请先配置微信数据目录")
            return

        if hasattr(self, 'scan_thread') and self.scan_thread.isRunning():
            self.setWarninginfo("正在扫描中，请稍候...")
            return

        self.clear_table()
        self.bar_progress.setValue(0)
        self.setSuccessinfo("正在扫描文件，请稍候...")

        config = load_config_file()
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
        check_state = Qt.Checked if state == Qt.Checked else Qt.Unchecked
        for row in range(self.table_files.rowCount()):
            item = self.table_files.item(row, 0)
            if item:
                item.setCheckState(check_state)

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
        self.total_size = 0

        share_thread_arr = [0]
        direct_delete = load_config_file().get("global", {}).get("direct_delete", False)
        thread = multiDeleteThread(selected_files, selected_dirs, share_thread_arr, direct_delete=direct_delete)
        thread.delete_process_signal.connect(self.callback)
        self.thread_list.append(thread)
        thread.start()

        self.remove_deleted_rows(selected_files, selected_dirs)

    def remove_deleted_rows(self, deleted_files, deleted_dirs):
        deleted = set(deleted_files + deleted_dirs)
        rows_to_remove = []
        for row in range(self.table_files.rowCount()):
            file_info = self.file_data[row]
            if file_info["path"] in deleted:
                rows_to_remove.append(row)

        for row in sorted(rows_to_remove, reverse=True):
            self.table_files.removeRow(row)
            del self.file_data[row]

    def make_empty_stats(self):
        return {
            "total_files": 0,
            "total_dirs": 0,
            "total_month_dirs": 0,
            "total_size": 0,
            "categories": {
                key: {"count": 0, "size": 0}
                for key in CATEGORY_NAME.keys()
            }
        }

    def merge_stats(self, total_stats, add_stats):
        total_stats["total_files"] += add_stats.get("total_files", 0)
        total_stats["total_dirs"] += add_stats.get("total_dirs", 0)
        total_stats["total_month_dirs"] += add_stats.get("total_month_dirs", 0)
        total_stats["total_size"] += add_stats.get("total_size", 0)
        for key, value in add_stats.get("categories", {}).items():
            total_stats["categories"].setdefault(key, {"count": 0, "size": 0})
            total_stats["categories"][key]["count"] += value.get("count", 0)
            total_stats["categories"][key]["size"] += value.get("size", 0)

    def build_whitelist(self, user_config):
        file_paths, file_exts = read_whitelist_file()
        cfg_paths = [os.path.abspath(os.path.expandvars(p)) for p in user_config.get("whitelist_paths", [])]
        cfg_exts = [normalize_ext(e) for e in user_config.get("whitelist_exts", [])]
        return file_paths + cfg_paths, set(file_exts + cfg_exts)

    def is_in_whitelist(self, file_path, whitelist_paths, whitelist_exts):
        ext = normalize_ext(os.path.splitext(str(file_path))[1])
        if is_protected_file_path(file_path):
            return True
        if ext in whitelist_exts:
            return True
        for p in whitelist_paths:
            if p and is_sub_path(file_path, p):
                return True
        return False

    def category_enabled(self, user_config, file_path, category, default_category):
        if user_config.get("use_advanced_ext_groups", False):
            ext_group = get_file_type(file_path, default_category)
            ext_groups = user_config.get("clean_ext_groups", {})
            if not ext_groups.get(ext_group, True):
                return False

        # 保留原来的四个勾选项逻辑，同时做更细的扩展名过滤。
        if category == "cache":
            return bool(user_config.get("clean_pic_cache", True))
        if category == "image":
            return bool(user_config.get("clean_pic", True))
        if category == "video":
            return bool(user_config.get("clean_video", True))
        if category in ("file", "document", "archive", "other"):
            return bool(user_config.get("clean_file", False))
        return True

    def add_file_if_match(self, file_path, now, day, category, file_list, file_set, stats, detail_lines, user_config, whitelist_paths, whitelist_exts):
        try:
            if not os.path.isfile(file_path):
                return
            # 程序组件和数据库文件始终跳过，避免把 dll/exe/db 一类文件送进回收站。
            if is_protected_file_path(file_path):
                return
            if user_config.get("use_whitelist", True) and self.is_in_whitelist(file_path, whitelist_paths, whitelist_exts):
                return
            timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            diff = (now - timestamp).days
            if diff < day:
                return
            real_category = get_file_type(file_path, category)
            # 日志、网页缓存这类路径即使扩展名普通，也归入缓存，方便用户理解。
            if category == "cache":
                real_category = "cache"
            if not self.category_enabled(user_config, file_path, real_category, category):
                return
            if file_path in file_set:
                return
            file_set.add(file_path)
            file_list.append(file_path)
            fsize = safe_file_size(file_path)
            stats["total_files"] += 1
            stats["total_size"] += fsize
            stats["categories"].setdefault(real_category, {"count": 0, "size": 0})
            stats["categories"][real_category]["count"] += 1
            stats["categories"][real_category]["size"] += fsize
            if len(detail_lines) < 1200:
                detail_lines.append(f"[{CATEGORY_NAME.get(real_category, real_category)}] {format_size(fsize)}  {file_path}")
        except Exception:
            logging.exception("扫描文件失败：%s", file_path)

    def is_expired_month_dir(self, dirname, now, day):
        match = re.match(r'^(?P<year>\d{4})-(?P<month>\d{2})$', dirname)
        if not match:
            return False
        try:
            year = int(match.group("year"))
            month = int(match.group("month"))
            if month < 1 or month > 12:
                return False
            if month == 12:
                next_month = datetime.datetime(year + 1, 1, 1)
            else:
                next_month = datetime.datetime(year, month + 1, 1)
            cutoff = now - datetime.timedelta(days=day)
            return next_month.date() <= cutoff.date()
        except Exception:
            return False

    def add_month_dir_if_expired(self, dir_path, dirname, now, day, category, dir_list, dir_set, stats, detail_lines, user_config, whitelist_paths):
        if not self.is_expired_month_dir(dirname, now, day):
            return False
        if not self.category_enabled(user_config, dir_path, category, category):
            return False
        if user_config.get("use_whitelist", True):
            for white_dir in whitelist_paths:
                if white_dir and is_sub_path(dir_path, white_dir):
                    return False
        if dir_path in dir_set:
            return True
        dir_set.add(dir_path)
        dir_list.append(dir_path)
        stats["total_month_dirs"] += 1
        stats["categories"].setdefault(category, {"count": 0, "size": 0})
        stats["categories"][category]["count"] += 1
        if len(detail_lines) < 1200:
            detail_lines.append(f"[旧月份文件夹] {CATEGORY_NAME.get(category, category)}  {dir_path}")
        return True

    def allow_month_dir_cleanup(self, root_path, category):
        if category != "file":
            return True
        parts = {part.lower() for part in Path(str(root_path)).parts}
        mixed_file_dirs = {"msgattach", "attach", "xwechat_files"}
        return not bool(parts & mixed_file_dirs)

    def scan_files_recursive(self, root_path, now, day, category, file_list, file_set, dir_list, dir_set, stats, detail_lines, user_config, whitelist_paths, whitelist_exts):
        # 用 os.walk 递归扫描，解决新版微信多层目录扫不到的问题。
        if not root_path or not os.path.exists(root_path):
            return
        try:
            allow_month_dirs = self.allow_month_dir_cleanup(root_path, category)
            for root, dirs, files in os.walk(root_path):
                # 程序组件目录不递归，防止把运行库和插件误当成缓存。
                dirs[:] = [d for d in dirs if d.lower() not in PROTECTED_DIR_NAMES]
                # 跳过白名单目录。
                skip_root = False
                if user_config.get("use_whitelist", True):
                    for white_dir in whitelist_paths:
                        if white_dir and is_sub_path(root, white_dir):
                            skip_root = True
                            break
                if skip_root:
                    dirs[:] = []
                    continue
                dirs_to_skip = []
                if allow_month_dirs:
                    for dirname in list(dirs):
                        dir_path = os.path.join(root, dirname)
                        if self.add_month_dir_if_expired(dir_path, dirname, now, day, category, dir_list, dir_set, stats, detail_lines, user_config, whitelist_paths):
                            dirs_to_skip.append(dirname)
                if dirs_to_skip:
                    dirs[:] = [d for d in dirs if d not in dirs_to_skip]
                for filename in files:
                    file_path = os.path.join(root, filename)
                    self.add_file_if_match(file_path, now, day, category, file_list, file_set, stats, detail_lines, user_config, whitelist_paths, whitelist_exts)
                    self.keep_ui_responsive()
                # 只记录真正的空旧目录，不整月粗暴删除，避免把白名单文件夹一起送进回收站。
                for dirname in list(dirs):
                    dir_path = os.path.join(root, dirname)
                    try:
                        if not os.listdir(dir_path):
                            timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(dir_path))
                            diff = (now - timestamp).days
                            if diff >= day and dir_path not in dir_set:
                                if not self.category_enabled(user_config, dir_path, category, category):
                                    continue
                                dir_set.add(dir_path)
                                dir_list.append(dir_path)
                                stats["total_dirs"] += 1
                                if len(detail_lines) < 1200:
                                    detail_lines.append(f"[空文件夹] {dir_path}")
                    except Exception:
                        logging.exception("扫描文件夹失败：%s", dir_path)
        except Exception:
            logging.exception("扫描目录失败：%s", root_path)

    def find_cache_dirs_under(self, base_path, max_depth=5):
        result = []
        if not base_path or not os.path.exists(base_path):
            return result
        base_depth = len(Path(base_path).parts)
        try:
            for root, dirs, files in os.walk(base_path):
                current_depth = len(Path(root).parts) - base_depth
                base_name = os.path.basename(root)
                lower_name = base_name.lower()
                if is_safe_cache_dir_name(lower_name):
                    result.append((root, "cache"))
                    # 当前目录已经是缓存目录，后续由 scan_files_recursive 负责递归。
                    dirs[:] = []
                    continue
                if current_depth >= max_depth:
                    dirs[:] = []
                    continue
                # 只继续往可能包含缓存的目录里找，不进入 runtime/web_shell/bin 等程序目录。
                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in PROTECTED_DIR_NAMES
                    and (is_safe_cache_dir_name(d) or 'cache' in d.lower() or 'log' in d.lower() or 'temp' in d.lower())
                ]
        except Exception:
            logging.exception("查找缓存目录失败：%s", base_path)
        return result

    def get_system_cache_dirs(self, client_type="wechat"):
        # 系统区只扫描明确的日志和缓存目录，不再扫描 web_shell、multitab 等运行组件目录。
        result = []
        appdata = os.environ.get("APPDATA")
        localappdata = os.environ.get("LOCALAPPDATA")
        candidates = []
        if client_type == "wxwork":
            if appdata:
                candidates.append(os.path.join(appdata, "Tencent", "WXWork"))
            if localappdata:
                candidates.append(os.path.join(localappdata, "Tencent", "WXWork"))
        else:
            if appdata:
                candidates.append(os.path.join(appdata, "Tencent", "WeChat"))
            if localappdata:
                candidates.append(os.path.join(localappdata, "Tencent", "WeChat"))

        for base in candidates:
            for name in ["log", "logs", "temp", "tmp"]:
                p = os.path.join(base, name)
                if os.path.exists(p):
                    result.append((p, "cache"))
            profiles = os.path.join(base, "radium", "web", "profiles")
            result.extend(self.find_cache_dirs_under(profiles, max_depth=6))
        return result

    def get_miniprogram_dirs(self, account_path):
        result = []
        if not account_path:
            return result
        parent = os.path.dirname(account_path)
        for base in [account_path, parent]:
            for name in ["Applet", "WMPF", "WeChatAppEx", "XPlugin"]:
                p = os.path.join(base, name)
                result.extend(self.find_cache_dirs_under(p, max_depth=5))
        return result

    def normalize_scan_dirs(self, scan_dirs):
        existing = []
        seen = set()
        for scan_path, category in scan_dirs:
            path = os.path.abspath(os.path.normpath(str(scan_path)))
            if not os.path.exists(path):
                continue
            key = (os.path.normcase(path), category)
            if key in seen:
                continue
            seen.add(key)
            existing.append((path, category))

        # If the same category already scans a parent directory, do not scan the nested child again.
        normalized = []
        for path, category in sorted(existing, key=lambda item: len(Path(item[0]).parts)):
            if any(category == parent_category and is_sub_path(path, parent_path)
                   for parent_path, parent_category in normalized):
                continue
            normalized.append((path, category))
        return normalized

    def get_fileNum(self, path, day, picCacheCheck, fileCheck, picCheck,
                    videoCheck, file_list, dir_list, user_config=None, stats=None, detail_lines=None, file_set=None, dir_set=None, include_system_cache=False):
        # 保留原函数名，内部增强为新版扫描逻辑，减少对原项目结构的影响。
        user_config = ensure_config_defaults({"users": [user_config or {}], "data_dir": [path], "global": {}})["users"][0]
        stats = stats if stats is not None else self.make_empty_stats()
        detail_lines = detail_lines if detail_lines is not None else []
        file_set = file_set if file_set is not None else set()
        dir_set = dir_set if dir_set is not None else set()
        correct_path = Path(os.path.normpath(path))
        now = datetime.datetime.now()
        client_type = user_config.get("client_type") or detect_client_type(str(correct_path))
        whitelist_paths, whitelist_exts = self.build_whitelist(user_config)

        scan_dirs = []
        if picCacheCheck:
            scan_dirs.append((correct_path / 'Attachment', 'cache'))
            scan_dirs.append((correct_path / 'FileStorage/Cache', 'cache'))
        if fileCheck:
            scan_dirs.append((correct_path / 'Files', 'file'))
            scan_dirs.append((correct_path / 'FileStorage/File', 'file'))
        if picCheck:
            scan_dirs.append((correct_path / 'Image/Image', 'image'))
            scan_dirs.append((correct_path / 'FileStorage/Image', 'image'))
        if videoCheck:
            scan_dirs.append((correct_path / 'Video', 'video'))
            scan_dirs.append((correct_path / 'FileStorage/Video', 'video'))

        if client_type == "wxwork" and user_config.get("clean_wxwork_cache", True):
            # 企业微信常见目录，部分版本会把文件、图片、语音按月份放在 Cache 下。
            if picCacheCheck:
                scan_dirs.append((correct_path / 'Cache', 'cache'))
                scan_dirs.extend(self.find_cache_dirs_under(str(correct_path / 'Cache'), max_depth=4))
            if fileCheck:
                scan_dirs.append((correct_path / 'File', 'file'))
                scan_dirs.append((correct_path / 'Files', 'file'))
                scan_dirs.append((correct_path / 'Document', 'document'))
            if picCheck:
                scan_dirs.append((correct_path / 'Image', 'image'))
                scan_dirs.append((correct_path / 'Images', 'image'))
            if videoCheck:
                scan_dirs.append((correct_path / 'Video', 'video'))
                scan_dirs.append((correct_path / 'Videos', 'video'))

        if 'xwechat_files' in str(correct_path).lower():
            if picCacheCheck:
                scan_dirs.append((correct_path / 'cache', 'cache'))
                scan_dirs.append((correct_path / 'temp', 'cache'))
                scan_dirs.append((correct_path / 'apm_record', 'cache'))
                scan_dirs.append((correct_path / 'business' / 'InputTemp', 'cache'))
                scan_dirs.append((correct_path / 'business' / 'emoticon' / 'Temp', 'cache'))
                scan_dirs.append((correct_path / 'business' / 'emoticon' / 'Thumb', 'cache'))
                scan_dirs.append((correct_path / 'business' / 'xweb', 'cache'))
            if fileCheck:
                scan_dirs.append((correct_path / 'msg' / 'file', 'file'))
                scan_dirs.append((correct_path / 'msg' / 'attach', 'file'))
                scan_dirs.append((correct_path / 'business' / 'favorite', 'file'))
            if videoCheck:
                scan_dirs.append((correct_path / 'msg' / 'video', 'video'))

        # 新版微信 4.x 常见附件目录，里面可能混合图片、视频和普通文件，实际分类按扩展名判断。
        if user_config.get("clean_msg_attach", True):
            scan_dirs.append((correct_path / 'FileStorage/MsgAttach', 'file'))
            scan_dirs.append((correct_path / 'MsgAttach', 'file'))
            scan_dirs.append((correct_path / 'msg/attach', 'file'))
            scan_dirs.append((correct_path / 'xwechat_files', 'file'))

        if picCacheCheck and user_config.get("clean_miniprogram_cache", True):
            scan_dirs.extend(self.get_miniprogram_dirs(str(correct_path)))

        if include_system_cache and picCacheCheck and user_config.get("clean_system_cache", True):
            scan_dirs.extend(self.get_system_cache_dirs(client_type))

        for scan_path, category in self.normalize_scan_dirs(scan_dirs):
            self.scan_files_recursive(str(scan_path), now, day, category, file_list, file_set, dir_list, dir_set, stats, detail_lines, user_config, whitelist_paths, whitelist_exts)

    # 原来的按月目录判断函数保留，避免旧代码引用时报错。
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
        # 保留旧函数，主流程已经换成递归扫描。
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
                if re.match(r'\d{4}-\d{2}', dirlist[i]) != None:
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

    def build_preview_text(self, total_stats, detail_lines):
        lines = []
        lines.append("清理前请确认")
        lines.append(f"预计可释放空间：{format_size(total_stats['total_size'])}")
        lines.append(
            f"将清理：{total_stats['total_files']} 个文件、"
            f"{total_stats.get('total_dirs', 0)} 个空文件夹、"
            f"{total_stats.get('total_month_dirs', 0)} 个旧月份文件夹"
        )
        lines.append("")
        lines.append("清理内容：")
        for key, name in CATEGORY_NAME.items():
            item = total_stats["categories"].get(key, {"count": 0, "size": 0})
            if item["count"] > 0:
                lines.append(f"- {name}：{item['count']} 个，{format_size(item['size'])}")
        if len(lines) == 5:
            lines.append("- 暂无分类数据")
        lines.append("")
        config = getattr(self, "config", {}) or {}
        if config.get("global", {}).get("direct_delete", False):
            lines.append("当前已开启直接删除，文件不会进入回收站。")
        else:
            lines.append("文件会先进入回收站，不会直接永久删除。")
        return "\n".join(lines)

    def parse_preview_detail_line(self, line):
        line = line.strip()
        if not line:
            return None
        if line.startswith("[空文件夹]"):
            return ("空文件夹", "-", line.replace("[空文件夹]", "", 1).strip())
        if line.startswith("[旧月份文件夹]"):
            content = line.replace("[旧月份文件夹]", "", 1).strip()
            parts = re.split(r'\s{2,}', content, maxsplit=1)
            if len(parts) == 2:
                return (f"旧月份文件夹/{parts[0]}", "-", parts[1])
            return ("旧月份文件夹", "-", content)
        match = re.match(r'^\[(?P<category>[^\]]+)\]\s+(?P<size>.+?)\s{2,}(?P<path>.+)$', line)
        if match:
            return (
                match.group("category").strip(),
                match.group("size").strip(),
                match.group("path").strip()
            )
        return ("其他", "-", line)

    def open_preview_path(self, table, row, column):
        if column != 2:
            return
        item = table.item(row, column)
        if not item:
            return
        target_path = item.data(Qt.UserRole) or item.text()
        if not target_path:
            return
        try:
            if os.path.exists(target_path):
                os.startfile(target_path)
            else:
                parent_path = os.path.dirname(target_path)
                if parent_path and os.path.isdir(parent_path):
                    os.startfile(parent_path)
                else:
                    self.setWarninginfo("文件不存在，可能已经被移动或删除。")
        except OSError as e:
            self.setWarninginfo(f"打开失败：{e}")

    def show_preview_dialog(self, total_stats, detail_lines):
        # 清理前预览，不再一点开始就直接进回收站。
        preview_text = self.build_preview_text(total_stats, detail_lines)
        try:
            with open(PREVIEW_PATH, "w", encoding="utf-8") as f:
                f.write(preview_text + "\n\n")
                f.write("详细文件列表：\n")
                f.write("\n".join(detail_lines))
        except Exception:
            logging.exception("写入扫描预览失败")

        dialog = QDialog(self)
        dialog.setWindowTitle("确认清理")
        dialog.setMinimumSize(820, 560)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #edf7f1;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                color: #21352b;
            }
            QLabel#previewTitle {
                color: #21352b;
                font-size: 22px;
                font-weight: 700;
            }
            QLabel#previewSubtitle {
                color: #5e7468;
                font-size: 13px;
            }
            QLabel#previewCard {
                color: #395246;
                background-color: #f8fbf7;
                border: 1px solid #dcebe1;
                border-radius: 14px;
                padding: 12px 14px;
                font-size: 13px;
            }
            QTableWidget {
                background-color: #f8fbf7;
                border: 1px solid #dcebe1;
                border-radius: 14px;
                gridline-color: #e2eee6;
                color: #31483d;
                font-size: 12px;
                selection-background-color: #e8f6ed;
                selection-color: #21352b;
            }
            QTableWidget::item {
                padding: 4px 6px;
            }
            QHeaderView::section {
                background-color: #e8f6ed;
                color: #486256;
                border: 0;
                border-bottom: 1px solid #d3e4d8;
                padding: 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton {
                min-height: 38px;
                padding: 0 18px;
                border-radius: 19px;
                font-size: 14px;
            }
            QPushButton#cancelPreview {
                color: #486256;
                background-color: #f1f7f3;
                border: 1px solid #d3e4d8;
            }
            QPushButton#confirmPreview {
                color: #f8fbf7;
                background-color: #16a85a;
                border: 1px solid #149550;
                font-weight: 600;
            }
            QPushButton#cancelPreview:hover {
                background-color: #e8f6ed;
                border-color: #b9dfc5;
            }
            QPushButton#confirmPreview:hover {
                background-color: #20b966;
                border-color: #18a75a;
            }
        """)

        root_layout = QVBoxLayout(dialog)
        root_layout.setContentsMargins(28, 24, 28, 22)
        root_layout.setSpacing(14)

        title = QLabel("清理前请确认")
        title.setObjectName("previewTitle")
        if self.config.get("global", {}).get("direct_delete", False):
            subtitle_text = "当前已开启直接删除，确认后文件不会进入回收站。"
        else:
            subtitle_text = "确认后文件会先进入回收站，不会直接永久删除。"
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("previewSubtitle")
        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)

        summary_layout = QGridLayout()
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(12)
        summary_items = [
            ("预计释放", format_size(total_stats.get("total_size", 0))),
            ("文件", f"{total_stats.get('total_files', 0)} 个"),
            ("空文件夹", f"{total_stats.get('total_dirs', 0)} 个"),
            ("旧月份文件夹", f"{total_stats.get('total_month_dirs', 0)} 个"),
        ]
        for index, (label, value) in enumerate(summary_items):
            card = QLabel(f"{label}\n{value}")
            card.setObjectName("previewCard")
            card.setAlignment(Qt.AlignCenter)
            summary_layout.addWidget(card, 0, index)
        root_layout.addLayout(summary_layout)

        category_lines = []
        for key, name in CATEGORY_NAME.items():
            item = total_stats["categories"].get(key, {"count": 0, "size": 0})
            if item["count"] > 0:
                category_lines.append(f"{name}：{item['count']} 个，{format_size(item['size'])}")
        if category_lines:
            category_label = QLabel("；".join(category_lines))
            category_label.setObjectName("previewSubtitle")
            category_label.setWordWrap(True)
            root_layout.addWidget(category_label)

        table = QTableWidget(dialog)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["类型", "大小", "路径"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setTextElideMode(Qt.ElideNone)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        table.setColumnWidth(0, 96)
        table.setColumnWidth(1, 92)
        table.setColumnWidth(2, 1200)

        rows = [self.parse_preview_detail_line(line) for line in detail_lines[:1200]]
        rows = [row for row in rows if row]
        table.setRowCount(len(rows))
        for row_index, (category, size, path) in enumerate(rows):
            for column_index, text in enumerate((category, size, path)):
                item = QTableWidgetItem(text)
                if column_index == 2:
                    item.setToolTip(text)
                    item.setData(Qt.UserRole, text)
                table.setItem(row_index, column_index, item)
        table.cellDoubleClicked.connect(lambda row, column: self.open_preview_path(table, row, column))
        root_layout.addWidget(table, 1)

        if len(detail_lines) > len(rows):
            more_label = QLabel(f"当前仅显示前 {len(rows)} 条，完整列表已保存到 {PREVIEW_PATH}")
            more_label.setObjectName("previewSubtitle")
            root_layout.addWidget(more_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        cancel_button = QPushButton("取消")
        cancel_button.setObjectName("cancelPreview")
        confirm_button = QPushButton("确认清理")
        confirm_button.setObjectName("confirmPreview")
        cancel_button.clicked.connect(dialog.reject)
        confirm_button.clicked.connect(dialog.accept)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(confirm_button)
        root_layout.addLayout(button_layout)

        return dialog.exec_() == QDialog.Accepted

    def callback(self, v):
        self.bar_progress.setRange(0, 100)
        total = int((self.total_file + self.total_dir))
        if total <= 0:
            self.bar_progress.setValue(0)
            return
        value = v / total * 100
        self.bar_progress.setValue(int(value))
        if value >= 100:
            out = "本次共清理文件" + str(self.total_file) + "个，文件夹" + str(
                self.total_dir) + "个，预计释放空间" + format_size(getattr(self, 'total_size', 0)) + "。\n请前往回收站检查并清空。"
            self.setSuccessinfo(out)
            self.thread_list = []
            if getattr(self, "auto_clean_running", False):
                state = load_json(STATE_PATH, {})
                state["last_auto_clean"] = datetime.datetime.now().strftime("%Y-%m-%d")
                save_json(STATE_PATH, state)
                self.auto_clean_running = False
            return

    def should_run_auto_clean(self, config):
        global_config = config.get("global", {})
        if not global_config.get("auto_clean_enable", False):
            return False
        state = load_json(STATE_PATH, {})
        last_auto_clean = state.get("last_auto_clean")
        try:
            interval = int(global_config.get("auto_clean_interval_days", 30))
        except Exception:
            interval = 30
        if not last_auto_clean:
            return True
        try:
            last_date = datetime.datetime.strptime(last_auto_clean, "%Y-%m-%d")
            return (datetime.datetime.now() - last_date).days >= interval
        except Exception:
            return True

    def justdoit(self, auto_mode=False):
        self.config = load_config_file()
        apply_startup_setting(self.config)
        need_clean = False
        self.thread_list = []
        self.scan_tick = 0
        self.bar_progress.setRange(0, 0)
        self.setSuccessinfo("正在扫描微信文件，请稍候...")
        QApplication.processEvents()
        total_file = 0
        total_dir = 0
        total_stats = self.make_empty_stats()
        detail_lines = []
        share_thread_arr = [0]
        system_cache_added = False

        for i, value in enumerate(self.config.get("users", [])):
            file_list = []
            dir_list = []
            stats = self.make_empty_stats()
            file_set = set()
            dir_set = set()
            if value.get("is_clean", False):
                account_dir = value.get("data_dir")
                if not account_dir and i < len(self.config.get("data_dir", [])):
                    account_dir = self.config["data_dir"][i]
                self.get_fileNum(account_dir,
                                 int(value.get("clean_days", 365)),
                                 value.get("clean_pic_cache", True), value.get("clean_file", False),
                                 value.get("clean_pic", True), value.get("clean_video", True),
                                 file_list, dir_list, user_config=value, stats=stats,
                                 detail_lines=detail_lines, file_set=file_set, dir_set=dir_set,
                                 include_system_cache=(not system_cache_added))
                system_cache_added = True

            if len(file_list) + len(dir_list) != 0:
                need_clean = True
                total_file += len(file_list)
                total_dir += len(dir_list)
                self.merge_stats(total_stats, stats)
                direct_delete = self.config.get("global", {}).get("direct_delete", False)
                thread = multiDeleteThread(file_list, dir_list, share_thread_arr, direct_delete=direct_delete)
                thread.delete_process_signal.connect(self.callback)
                self.thread_list.append(thread)

        if not need_clean:
            self.bar_progress.setRange(0, 100)
            self.bar_progress.setValue(0)
            self.setWarninginfo("没有需要清理的文件")
        else:
            self.total_file = total_file
            self.total_dir = total_dir
            self.total_size = total_stats.get("total_size", 0)
            self.bar_progress.setRange(0, 100)
            self.bar_progress.setValue(0)
            if not auto_mode or self.config.get("global", {}).get("auto_clean_confirm", True):
                if not self.show_preview_dialog(total_stats, detail_lines):
                    self.setWarninginfo("已取消清理，未移动任何文件。")
                    self.thread_list = []
                    return
            self.setSuccessinfo("正在清理中，请稍候...")
            # 真正启动 QThread，并保存线程对象，避免界面卡死和线程被回收。
            for thread in self.thread_list:
                thread.start()

    def show_config_window(self):
        self.config_window = ConfigWindow()
        self.setSuccessinfo("已经准备好，可以开始了！")

    def create_config_from_paths(self, paths):
        user_config = []
        data_dirs = []
        existing_user_config_dic = existing_user_config()
        seen_users = set()

        for path in paths:
            dir_list, user_list = get_dir_name(path)
            for index, user_wx_id in enumerate(user_list):
                if user_wx_id in seen_users:
                    continue
                seen_users.add(user_wx_id)
                user_dir = dir_list[index]
                data_dirs.append(user_dir)
                if user_wx_id in existing_user_config_dic:
                    uc = existing_user_config_dic[user_wx_id]
                    uc["data_dir"] = user_dir
                    uc["client_type"] = detect_client_type(user_dir)
                    user_config.append(uc)
                else:
                    user_config.append(make_default_user_config(user_wx_id, user_dir))

        if not user_config:
            return None
        return ensure_config_defaults({"data_dir": data_dirs, "users": user_config})

    def smart_detect_wechat_path(self):
        config = self.create_config_from_paths(find_all_wechat_paths())
        if not config:
            return False
        save_json(CONFIG_PATH, config)
        self.config_exists = True
        self.setSuccessinfo("已自动检测到微信数据目录，可以开始清理。")
        return True

    def check_auto_clean_after_start(self):
        try:
            if os.path.exists(CONFIG_PATH):
                config = load_config_file()
                apply_startup_setting(config)
                if "--startup" not in sys.argv:
                    return
                if self.should_run_auto_clean(config):
                    self.auto_clean_running = True
                    self.setSuccessinfo("已到自动清理周期，正在扫描...")
                    self.justdoit(auto_mode=True)
        except Exception:
            logging.exception("自动清理检查失败")

    def __init__(self):
        super().__init__()
        loadUi(working_dir + "/images/main.ui", self)

        self._frame()
        self._eventfilter()
        if hasattr(self, "table_files"):
            self.init_table()
        if hasattr(self, "check_select_all"):
            self.check_select_all.stateChanged.connect(self.toggle_select_all)
        self.simplify_home_ui()
        self.doFadeIn()
        self.config_exists = True
        self.thread_list = []
        self.auto_clean_running = False
        ensure_whitelist_file()
        self.show()

        # 判断配置文件是否存在
        if not os.path.exists(CONFIG_PATH):
            self.setWarninginfo("首次使用，即将自动弹出配置窗口")
            self.config_exists = False

            timer = QTimer(self)
            def detect_or_configure():
                if not self.smart_detect_wechat_path():
                    self.show_config_window()

            timer.timeout.connect(detect_or_configure)
            timer.setSingleShot(True)  # 只执行一次
            
            # 设置定时器的时间间隔，这里设置为 1000ms（1秒）
            timer.start(500)
        else:
            # 如果用户在 config.json 开启自动清理，则启动后按周期检查。
            timer = QTimer(self)
            timer.timeout.connect(self.check_auto_clean_after_start)
            timer.setSingleShot(True)
            timer.start(800)


if __name__ == '__main__':
    app = QApplication([])
    win = MainWindow()
    app.exec_()
