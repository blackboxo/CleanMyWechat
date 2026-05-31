import sys
import traceback
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QDesktopServices
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.macos_wechat import (
    DEFAULT_CUTOFF_MONTH,
    create_symlink_view,
    default_xwechat_root,
    scan_macos_wechat,
    write_dashboard,
    write_markdown_summary,
    write_scan_outputs,
)


class ScanWorker(QThread):
    message = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, source, output, cutoff_month):
        super().__init__()
        self.source = Path(source).expanduser()
        self.output = Path(output).expanduser()
        self.cutoff_month = cutoff_month

    def emit_scan_progress(self, event):
        percent = int(event.get("percent", 0))
        scaled = min(90, max(1, 1 + int(percent * 0.89)))
        self.progress.emit(scaled, event.get("message", "正在扫描"))

    def run(self):
        try:
            self.progress.emit(1, "准备扫描")
            scan = scan_macos_wechat(self.source, cutoff_month=self.cutoff_month, progress_callback=self.emit_scan_progress)

            reports_dir = self.output / "reports"
            dashboard_path = self.output / "dashboard/wechat_dashboard.html"
            summary_path = reports_dir / "macos_wechat_summary.md"
            view_dir = self.output / "organized_view"

            self.progress.emit(92, "正在写入报告")
            outputs = write_scan_outputs(scan, reports_dir)
            write_markdown_summary(scan, summary_path)

            self.progress.emit(95, "正在生成 Dashboard")
            write_dashboard(scan, dashboard_path)

            self.progress.emit(98, "正在创建整理视图")
            view_result = create_symlink_view(scan, view_dir)

            self.progress.emit(100, "完成")
            self.finished_ok.emit(
                {
                    "accounts": len(scan["accounts"]),
                    "files": scan["summary"]["file_count"],
                    "visible_size": scan["summary"]["total_size"],
                    "duplicates": scan["summary"]["duplicate_group_count"],
                    "duplicate_savings": scan["summary"]["duplicate_potential_savings"],
                    "dashboard": str(dashboard_path),
                    "summary": str(summary_path),
                    "json": outputs["json"],
                    "view": view_result["root"],
                }
            )
        except Exception:
            self.failed.emit(traceback.format_exc())


class MacOSWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.dashboard_path = ""
        self.view_path = ""
        self.output_path = str(Path.home() / "Documents/CleanMyWechat-macOS")
        self.setWindowTitle("微信空间检查 Dashboard")
        self.resize(940, 680)
        self.setMinimumSize(840, 600)
        self.build_ui()
        self.apply_theme()

    def build_ui(self):
        central = QWidget()
        central.setObjectName("AppBackground")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("GlassShell")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(37, 55, 72, 46))
        shell.setGraphicsEffect(shadow)
        layout.addWidget(shell)

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(18, 16, 18, 16)
        shell_layout.setSpacing(12)

        heading = QHBoxLayout()
        heading.setSpacing(12)
        shell_layout.addLayout(heading)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(3)
        heading.addLayout(title_stack, 1)

        title = QLabel("微信空间检查")
        title.setObjectName("Title")
        title_stack.addWidget(title)

        caption = QLabel("Clean My WeChat macOS · 只读模式")
        caption.setObjectName("Caption")
        title_stack.addWidget(caption)

        badge = QLabel("不移动 · 不删除 · 不重命名")
        badge.setObjectName("SafetyBadge")
        badge.setAlignment(Qt.AlignCenter)
        heading.addWidget(badge)

        form_panel = QFrame()
        form_panel.setObjectName("GlassPanel")
        shell_layout.addWidget(form_panel)
        grid = QGridLayout(form_panel)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        self.source_edit = QLineEdit(str(default_xwechat_root()))
        self.output_edit = QLineEdit(self.output_path)
        self.cutoff_edit = QLineEdit(DEFAULT_CUTOFF_MONTH)
        self.cutoff_edit.setMaximumWidth(130)

        grid.addWidget(QLabel("微信数据目录"), 0, 0)
        grid.addWidget(self.source_edit, 0, 1)
        source_button = self.make_button("选择", self.choose_source)
        grid.addWidget(source_button, 0, 2)

        grid.addWidget(QLabel("输出目录"), 1, 0)
        grid.addWidget(self.output_edit, 1, 1)
        output_button = self.make_button("选择", self.choose_output)
        grid.addWidget(output_button, 1, 2)

        grid.addWidget(QLabel("候选月份阈值"), 2, 0)
        grid.addWidget(self.cutoff_edit, 2, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        shell_layout.addLayout(actions)

        self.scan_button = self.make_button("扫描并生成 Dashboard", self.run_scan, primary=True)
        actions.addWidget(self.scan_button)
        actions.addWidget(self.make_button("打开 Dashboard", self.open_dashboard))
        actions.addWidget(self.make_button("打开整理视图", self.open_view))
        actions.addStretch(1)
        actions.addWidget(self.make_button("打开输出目录", self.open_output))

        progress_panel = QFrame()
        progress_panel.setObjectName("GlassPanel")
        shell_layout.addWidget(progress_panel)
        progress_layout = QVBoxLayout(progress_panel)
        progress_layout.setContentsMargins(14, 12, 14, 12)
        progress_layout.setSpacing(8)

        status_row = QHBoxLayout()
        self.status_label = QLabel("待扫描")
        self.status_label.setObjectName("StatusLabel")
        self.metrics_label = QLabel("")
        self.metrics_label.setObjectName("MetricsLabel")
        self.metrics_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.metrics_label)
        progress_layout.addLayout(status_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("LogArea")
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(220)
        shell_layout.addWidget(self.log_area, 1)

        self.log("准备就绪。当前流程只生成统计、Dashboard 和符号链接整理视图。")
        self.log(f"默认数据目录：{self.source_edit.text()}")

    def make_button(self, text, slot, primary=False):
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(slot)
        button.setObjectName("PrimaryButton" if primary else "SecondaryButton")
        return button

    def apply_theme(self):
        self.setStyleSheet(
            """
            QWidget#AppBackground {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f7fbfb, stop:0.46 #e7eff4, stop:1 #f5f8f1);
                color: #17212b;
                font-family: "PingFang SC", "Hiragino Sans GB", "Segoe UI";
                font-size: 13px;
            }
            QFrame#GlassShell {
                background-color: rgba(255, 255, 255, 178);
                border: 1px solid rgba(255, 255, 255, 218);
                border-radius: 8px;
            }
            QFrame#GlassPanel {
                background-color: rgba(255, 255, 255, 158);
                border: 1px solid rgba(255, 255, 255, 218);
                border-radius: 8px;
            }
            QLabel#Title {
                font-size: 24px;
                font-weight: 850;
                color: #17212b;
            }
            QLabel#Caption, QLabel#MetricsLabel {
                color: #66727e;
            }
            QLabel#SafetyBadge {
                color: #0b6f75;
                background-color: rgba(11, 127, 134, 24);
                border: 1px solid rgba(11, 127, 134, 56);
                border-radius: 8px;
                padding: 7px 10px;
                font-weight: 750;
            }
            QLabel#StatusLabel {
                color: #17212b;
                font-weight: 750;
            }
            QLineEdit {
                min-height: 34px;
                border: 1px solid rgba(104, 122, 141, 82);
                border-radius: 6px;
                padding: 6px 9px;
                background-color: rgba(255, 255, 255, 205);
                selection-background-color: #0b7f86;
            }
            QLineEdit:focus {
                border: 1px solid #0b7f86;
            }
            QPushButton {
                min-height: 34px;
                border-radius: 7px;
                padding: 6px 12px;
                font-weight: 750;
            }
            QPushButton#PrimaryButton {
                color: white;
                background-color: #0b7f86;
                border: 1px solid #096f76;
            }
            QPushButton#PrimaryButton:hover {
                background-color: #0f8f94;
            }
            QPushButton#PrimaryButton:disabled {
                background-color: #9cb3b6;
                border-color: #9cb3b6;
            }
            QPushButton#SecondaryButton {
                color: #17212b;
                background-color: rgba(255, 255, 255, 190);
                border: 1px solid rgba(112, 130, 148, 78);
            }
            QPushButton#SecondaryButton:hover {
                background-color: rgba(255, 255, 255, 235);
                border-color: rgba(11, 127, 134, 110);
            }
            QProgressBar {
                height: 14px;
                border: 1px solid rgba(112, 130, 148, 70);
                border-radius: 7px;
                background-color: rgba(119, 139, 157, 30);
                text-align: center;
                color: #17212b;
                font-size: 11px;
                font-weight: 700;
            }
            QProgressBar::chunk {
                border-radius: 7px;
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0b7f86, stop:0.62 #3f7f5a, stop:1 #b06218);
            }
            QTextEdit#LogArea {
                background-color: rgba(255, 255, 255, 174);
                border: 1px solid rgba(255, 255, 255, 218);
                border-radius: 8px;
                padding: 8px;
                color: #24313e;
                selection-background-color: #0b7f86;
            }
            """
        )

    def log(self, text):
        self.log_area.append(text)

    def choose_source(self):
        path = QFileDialog.getExistingDirectory(self, "选择微信 xwechat_files 文件夹", self.source_edit.text())
        if path:
            self.source_edit.setText(path)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_edit.text())
        if path:
            self.output_edit.setText(path)

    def run_scan(self):
        source = Path(self.source_edit.text()).expanduser()
        output = Path(self.output_edit.text()).expanduser()
        cutoff = self.cutoff_edit.text().strip()
        if len(cutoff) != 7 or cutoff[4] != "-":
            QMessageBox.warning(self, "月份格式无效", "请使用 YYYY-MM，例如 2025-06。")
            return
        if not source.exists():
            QMessageBox.warning(self, "找不到数据目录", f"数据目录不存在：\n{source}")
            return

        self.scan_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("准备扫描")
        self.metrics_label.setText("")
        self.output_path = str(output)
        self.worker = ScanWorker(source, output, cutoff)
        self.worker.progress.connect(self.scan_progress)
        self.worker.message.connect(self.log)
        self.worker.finished_ok.connect(self.scan_done)
        self.worker.failed.connect(self.scan_failed)
        self.worker.start()

    def scan_progress(self, percent, message):
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)
        if message:
            self.log(f"[{percent:3d}%] {message}")

    def scan_done(self, result):
        self.scan_button.setEnabled(True)
        self.dashboard_path = result["dashboard"]
        self.view_path = result["view"]
        self.metrics_label.setText(
            f"{result['accounts']} 个账号 · {result['files']} 个文件 · {result['duplicates']} 组重复"
        )
        self.log(f"账号数量：{result['accounts']}")
        self.log(f"可见文件：{result['files']} / {result['visible_size']}")
        self.log(f"重复大文件：{result['duplicates']} 组 / 理论可节省 {result['duplicate_savings']}")
        self.log(f"Dashboard：{result['dashboard']}")
        self.log(f"整理视图：{result['view']}")
        self.log(f"摘要：{result['summary']}")
        self.log(f"JSON：{result['json']}")
        QMessageBox.information(self, "Dashboard 已生成", "macOS 微信文件 Dashboard 已生成。")

    def scan_failed(self, details):
        self.scan_button.setEnabled(True)
        self.status_label.setText("扫描失败")
        self.log(details)
        QMessageBox.critical(self, "扫描失败", details)

    def open_local_path(self, path):
        if not path:
            QMessageBox.information(self, "结果未生成", "请先扫描生成结果。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).expanduser())))

    def open_dashboard(self):
        candidate = self.dashboard_path or str(Path(self.output_edit.text()).expanduser() / "dashboard/wechat_dashboard.html")
        self.open_local_path(candidate if Path(candidate).exists() else "")

    def open_view(self):
        candidate = self.view_path or str(Path(self.output_edit.text()).expanduser() / "organized_view")
        self.open_local_path(candidate if Path(candidate).exists() else "")

    def open_output(self):
        output = Path(self.output_edit.text()).expanduser()
        output.mkdir(parents=True, exist_ok=True)
        self.open_local_path(output)


def main():
    app = QApplication(sys.argv)
    window = MacOSWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
