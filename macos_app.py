import sys
import traceback
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QDesktopServices
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.macos_wechat import (
    DEFAULT_CLEANUP_OPTIONS,
    DEFAULT_CUTOFF_MONTH,
    build_cleanup_plan,
    category_label,
    compare_scan_results,
    create_symlink_view,
    default_xwechat_root,
    human_size,
    load_scan_history,
    load_scan_result,
    record_scan_history,
    scan_macos_wechat,
    trash_cleanup_plan,
    write_dashboard,
    write_markdown_summary,
    write_scan_outputs,
)


def now_label():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class ScanWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, source, output, cutoff_month, previous_scan=None):
        super().__init__()
        self.source = Path(source).expanduser() if source else None
        self.output = Path(output).expanduser()
        self.cutoff_month = cutoff_month
        self.previous_scan = previous_scan

    def emit_scan_progress(self, event):
        percent = int(event.get("percent", 0))
        scaled = min(90, max(1, 1 + int(percent * 0.89)))
        self.progress.emit(scaled, event.get("message", "正在扫描"))

    def run(self):
        try:
            self.progress.emit(1, "准备扫描")
            scan = scan_macos_wechat(self.source, cutoff_month=self.cutoff_month, progress_callback=self.emit_scan_progress)
            diff = compare_scan_results(self.previous_scan, scan) if self.previous_scan else {}

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
            history_entry = record_scan_history(
                self.output,
                scan,
                outputs,
                dashboard_path=dashboard_path,
                summary_path=summary_path,
                view_path=view_result["root"],
                diff=diff,
            )

            self.progress.emit(100, "完成")
            self.finished_ok.emit(
                {
                    "scan": scan,
                    "diff": diff,
                    "history_entry": history_entry,
                    "dashboard": str(dashboard_path),
                    "summary": str(summary_path),
                    "json": outputs["json"],
                    "view": view_result["root"],
                }
            )
        except Exception:
            self.failed.emit(traceback.format_exc())


class CleanupWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, plan, selected_paths):
        super().__init__()
        self.plan = plan
        self.selected_paths = selected_paths

    def run(self):
        try:
            result = trash_cleanup_plan(self.plan, self.selected_paths, progress_callback=self.progress.emit)
            self.finished_ok.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())


class MacOSWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.cleanup_worker = None
        self.scan_result = None
        self.cleanup_plan = None
        self.diff_result = {}
        self.dashboard_path = ""
        self.view_path = ""
        self.output_path = str(Path.home() / "Documents/CleanMyWechat-macOS")
        self.setWindowTitle("微信空间检查 Dashboard")
        self.resize(1100, 760)
        self.setMinimumSize(960, 660)
        self.build_ui()
        self.apply_theme()
        self.refresh_history()

    def build_ui(self):
        central = QWidget()
        central.setObjectName("AppBackground")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 18, 20, 18)

        shell = QFrame()
        shell.setObjectName("GlassShell")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(37, 55, 72, 46))
        shell.setGraphicsEffect(shadow)
        outer.addWidget(shell)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        heading = QHBoxLayout()
        layout.addLayout(heading)
        title_stack = QVBoxLayout()
        heading.addLayout(title_stack, 1)
        title = QLabel("微信空间检查")
        title.setObjectName("Title")
        title_stack.addWidget(title)
        caption = QLabel("Clean My WeChat macOS · 扫描、复查、预览后清理")
        caption.setObjectName("Caption")
        title_stack.addWidget(caption)
        self.safe_badge = QLabel("默认移动到回收站")
        self.safe_badge.setObjectName("SafetyBadge")
        self.safe_badge.setAlignment(Qt.AlignCenter)
        heading.addWidget(self.safe_badge)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("GlassTabs")
        layout.addWidget(self.tabs, 1)

        self.build_scan_tab()
        self.build_overview_tab()
        self.build_files_tab()
        self.build_candidates_tab()
        self.build_duplicates_tab()
        self.build_history_tab()

    def build_scan_tab(self):
        tab = QWidget()
        body = QVBoxLayout(tab)
        body.setSpacing(12)

        form = self.panel()
        grid = QGridLayout(form)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        self.source_edit = QLineEdit("AUTO")
        self.source_edit.setPlaceholderText(str(default_xwechat_root()))
        self.output_edit = QLineEdit(self.output_path)
        self.cutoff_edit = QLineEdit(DEFAULT_CUTOFF_MONTH)
        self.cutoff_edit.setMaximumWidth(130)

        grid.addWidget(QLabel("微信数据目录"), 0, 0)
        grid.addWidget(self.source_edit, 0, 1)
        grid.addWidget(self.make_button("选择", self.choose_source), 0, 2)
        grid.addWidget(QLabel("输出目录"), 1, 0)
        grid.addWidget(self.output_edit, 1, 1)
        grid.addWidget(self.make_button("选择", self.choose_output), 1, 2)
        grid.addWidget(QLabel("候选月份阈值"), 2, 0)
        grid.addWidget(self.cutoff_edit, 2, 1)
        body.addWidget(form)

        actions = QHBoxLayout()
        self.scan_button = self.make_button("扫描并保存", self.run_scan, primary=True)
        actions.addWidget(self.scan_button)
        actions.addWidget(self.make_button("增量对比扫描", self.run_incremental_scan))
        actions.addWidget(self.make_button("加载扫描 JSON", self.load_scan_json))
        actions.addWidget(self.make_button("打开 Dashboard", self.open_dashboard))
        actions.addWidget(self.make_button("打开整理视图", self.open_view))
        actions.addStretch(1)
        actions.addWidget(self.make_button("打开输出目录", self.open_output))
        body.addLayout(actions)

        progress = self.panel()
        progress_layout = QVBoxLayout(progress)
        progress_layout.setContentsMargins(14, 12, 14, 12)
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
        progress_layout.addWidget(self.progress_bar)
        body.addWidget(progress)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("LogArea")
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(220)
        body.addWidget(self.log_area, 1)
        self.tabs.addTab(tab, "扫描")

        self.log("准备就绪。可以扫描、加载旧结果，或基于旧结果做增量对比扫描。")
        self.log("默认数据目录：AUTO（自动识别常见微信/企业微信目录）")

    def build_overview_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.kpi_frame = self.panel()
        self.kpi_grid = QGridLayout(self.kpi_frame)
        self.kpi_grid.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(self.kpi_frame)
        self.account_table = self.table(["账号", "大小", "路径", "最大分区"])
        layout.addWidget(self.account_table, 1)
        self.tabs.addTab(tab, "概览")

    def build_files_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        toolbar = QHBoxLayout()
        self.file_filter = QLineEdit()
        self.file_filter.setPlaceholderText("搜索文件名、类型、月份或路径")
        self.file_filter.textChanged.connect(self.populate_files)
        toolbar.addWidget(self.file_filter, 1)
        toolbar.addWidget(self.make_button("打开选中文件", self.open_selected_file))
        layout.addLayout(toolbar)
        self.file_table = self.table(["文件", "类型", "来源", "月份", "大小", "路径"])
        layout.addWidget(self.file_table, 1)
        self.tabs.addTab(tab, "文件")

    def build_candidates_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        settings = self.panel()
        settings_layout = QGridLayout(settings)
        settings_layout.setContentsMargins(14, 12, 14, 12)
        self.retention_edit = QLineEdit("365")
        self.retention_edit.setMaximumWidth(90)
        self.clean_images_check = QCheckBox("图片")
        self.clean_images_check.setChecked(True)
        self.clean_videos_check = QCheckBox("视频")
        self.clean_videos_check.setChecked(True)
        self.clean_files_check = QCheckBox("文件")
        self.clean_files_check.setChecked(False)
        self.clean_cache_check = QCheckBox("缓存")
        self.clean_cache_check.setChecked(True)
        self.use_whitelist_check = QCheckBox("启用白名单")
        self.use_whitelist_check.setChecked(True)
        self.whitelist_exts_edit = QLineEdit(",".join(DEFAULT_CLEANUP_OPTIONS["whitelist_exts"]))
        self.whitelist_exts_edit.setPlaceholderText(".doc,.docx,.xlsx,.pdf")
        self.whitelist_paths_edit = QLineEdit("")
        self.whitelist_paths_edit.setPlaceholderText("白名单路径，多个用逗号分隔")
        self.auto_clean_check = QCheckBox("定期自动清理")
        self.auto_days_edit = QLineEdit("30")
        self.auto_days_edit.setMaximumWidth(80)
        settings_layout.addWidget(QLabel("保留天数"), 0, 0)
        settings_layout.addWidget(self.retention_edit, 0, 1)
        settings_layout.addWidget(self.clean_images_check, 0, 2)
        settings_layout.addWidget(self.clean_videos_check, 0, 3)
        settings_layout.addWidget(self.clean_files_check, 0, 4)
        settings_layout.addWidget(self.clean_cache_check, 0, 5)
        settings_layout.addWidget(self.use_whitelist_check, 1, 0)
        settings_layout.addWidget(QLabel("白名单扩展名"), 1, 1)
        settings_layout.addWidget(self.whitelist_exts_edit, 1, 2, 1, 2)
        settings_layout.addWidget(QLabel("白名单路径"), 2, 0)
        settings_layout.addWidget(self.whitelist_paths_edit, 2, 1, 1, 3)
        settings_layout.addWidget(self.auto_clean_check, 3, 0)
        settings_layout.addWidget(QLabel("清理间隔天数"), 3, 1)
        settings_layout.addWidget(self.auto_days_edit, 3, 2)
        settings_layout.addWidget(QLabel("按类型 + 保留天数预览，确认后移入回收站。"), 3, 3, 1, 3)
        layout.addWidget(settings)

        actions = QHBoxLayout()
        actions.addWidget(self.make_button("全选候选桶", self.select_all_candidates))
        actions.addWidget(self.make_button("生成清理预览", self.preview_cleanup, primary=True))
        actions.addWidget(self.make_button("移动所选到回收站", self.execute_cleanup))
        actions.addStretch(1)
        self.cleanup_label = QLabel("尚未生成清理预览")
        self.cleanup_label.setObjectName("MetricsLabel")
        actions.addWidget(self.cleanup_label)
        layout.addLayout(actions)
        self.candidate_table = self.table(["选择", "类别", "账号", "月份", "大小", "说明", "路径"])
        layout.addWidget(self.candidate_table, 1)
        self.cleanup_table = self.table(["选择", "文件", "类别", "月份", "大小", "路径"])
        layout.addWidget(self.cleanup_table, 1)
        self.tabs.addTab(tab, "候选清理")

    def build_duplicates_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.duplicate_table = self.table(["组", "份数", "单个大小", "理论节省", "示例路径"])
        layout.addWidget(self.duplicate_table, 1)
        self.tabs.addTab(tab, "重复")

    def build_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        actions = QHBoxLayout()
        actions.addWidget(self.make_button("刷新历史", self.refresh_history))
        actions.addWidget(self.make_button("加载选中历史", self.load_selected_history, primary=True))
        actions.addStretch(1)
        layout.addLayout(actions)
        self.history_table = self.table(["生成时间", "文件数", "总大小", "新增", "变化", "JSON"])
        layout.addWidget(self.history_table, 1)
        self.tabs.addTab(tab, "历史")

    def panel(self):
        frame = QFrame()
        frame.setObjectName("GlassPanel")
        return frame

    def table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        return table

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
            QFrame#GlassShell, QFrame#GlassPanel, QTabWidget::pane, QTableWidget, QTextEdit#LogArea {
                background-color: rgba(255, 255, 255, 178);
                border: 1px solid rgba(255, 255, 255, 218);
                border-radius: 8px;
            }
            QTabBar::tab {
                min-height: 28px;
                padding: 7px 14px;
                margin-right: 4px;
                border-radius: 7px;
                color: #66727e;
                font-weight: 750;
                background-color: rgba(255, 255, 255, 110);
            }
            QTabBar::tab:selected {
                color: #17212b;
                background-color: rgba(255, 255, 255, 230);
                border: 1px solid rgba(255, 255, 255, 235);
            }
            QLabel#Title { font-size: 24px; font-weight: 850; color: #17212b; }
            QLabel#Caption, QLabel#MetricsLabel { color: #66727e; }
            QLabel#SafetyBadge {
                color: #0b6f75;
                background-color: rgba(11, 127, 134, 24);
                border: 1px solid rgba(11, 127, 134, 56);
                border-radius: 8px;
                padding: 7px 10px;
                font-weight: 750;
            }
            QLabel#StatusLabel { color: #17212b; font-weight: 750; }
            QLineEdit {
                min-height: 34px;
                border: 1px solid rgba(104, 122, 141, 82);
                border-radius: 6px;
                padding: 6px 9px;
                background-color: rgba(255, 255, 255, 205);
                selection-background-color: #0b7f86;
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
            QPushButton#SecondaryButton {
                color: #17212b;
                background-color: rgba(255, 255, 255, 190);
                border: 1px solid rgba(112, 130, 148, 78);
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
            QHeaderView::section {
                background-color: rgba(255,255,255,210);
                border: 0;
                border-bottom: 1px solid rgba(114,133,151,70);
                padding: 7px;
                color: #66727e;
                font-weight: 750;
            }
            QTableWidget {
                gridline-color: rgba(114,133,151,70);
                alternate-background-color: rgba(255,255,255,110);
                selection-background-color: rgba(11,127,134,48);
            }
            QTextEdit#LogArea {
                padding: 8px;
                color: #24313e;
                selection-background-color: #0b7f86;
            }
            """
        )

    def log(self, text):
        self.log_area.append(f"{now_label()} {text}")

    def choose_source(self):
        start = str(default_xwechat_root()) if self.source_edit.text().strip().upper() == "AUTO" else self.source_edit.text()
        path = QFileDialog.getExistingDirectory(self, "选择微信 xwechat_files 文件夹", start)
        if path:
            self.source_edit.setText(path)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_edit.text())
        if path:
            self.output_edit.setText(path)
            self.output_path = path
            self.refresh_history()

    def validate_inputs(self):
        source_text = self.source_edit.text().strip()
        source = None if not source_text or source_text.upper() == "AUTO" else Path(source_text).expanduser()
        cutoff = self.cutoff_edit.text().strip()
        if len(cutoff) != 7 or cutoff[4] != "-":
            QMessageBox.warning(self, "月份格式无效", "请使用 YYYY-MM，例如 2025-06。")
            return None
        if source is not None and not source.exists():
            QMessageBox.warning(self, "找不到数据目录", f"数据目录不存在：\n{source}")
            return None
        return source, Path(self.output_edit.text()).expanduser(), cutoff

    def run_scan(self):
        values = self.validate_inputs()
        if not values:
            return
        self.start_scan(*values, previous_scan=None)

    def run_incremental_scan(self):
        values = self.validate_inputs()
        if not values:
            return
        previous = self.scan_result
        if not previous:
            history = load_scan_history(values[1])
            if history and history[0].get("json"):
                previous = load_scan_result(history[0]["json"])
        if not previous:
            QMessageBox.information(self, "没有旧扫描", "请先完成一次扫描或加载历史 JSON。")
            return
        self.start_scan(*values, previous_scan=previous)

    def start_scan(self, source, output, cutoff, previous_scan=None):
        self.output_path = str(output)
        self.scan_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("准备扫描")
        self.metrics_label.setText("")
        self.worker = ScanWorker(source, output, cutoff, previous_scan=previous_scan)
        self.worker.progress.connect(self.scan_progress)
        self.worker.finished_ok.connect(self.scan_done)
        self.worker.failed.connect(self.scan_failed)
        self.worker.start()

    def scan_progress(self, percent, message):
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)
        self.log(f"[{percent:3d}%] {message}")

    def scan_done(self, result):
        self.scan_button.setEnabled(True)
        self.dashboard_path = result["dashboard"]
        self.view_path = result["view"]
        self.populate_scan(result["scan"], result.get("json", ""), result.get("diff", {}))
        self.refresh_history()
        self.log(f"扫描结果已保存：{result['json']}")
        QMessageBox.information(self, "扫描完成", "结果已保存，可以在各个 Tab 中继续查看。")

    def scan_failed(self, details):
        self.scan_button.setEnabled(True)
        self.status_label.setText("扫描失败")
        self.log(details)
        QMessageBox.critical(self, "扫描失败", details)

    def populate_scan(self, scan, json_path="", diff=None):
        self.scan_result = scan
        self.diff_result = diff or {}
        summary = scan.get("summary", {})
        self.metrics_label.setText(
            f"{len(scan.get('accounts', []))} 个账号 · {summary.get('file_count', 0)} 个文件 · "
            f"{summary.get('duplicate_group_count', 0)} 组重复"
        )
        self.status_label.setText(f"已加载：{scan.get('generated_at', '')}")
        self.progress_bar.setValue(100)
        self.populate_overview()
        self.populate_files()
        self.populate_candidates()
        self.populate_duplicates()
        self.cleanup_plan = None
        self.cleanup_table.setRowCount(0)
        self.cleanup_label.setText("尚未生成清理预览")
        if diff:
            self.log(
                "增量对比："
                f"新增 {diff.get('added_count', 0)} 个 / {diff.get('added_size', '0 B')}，"
                f"变化 {diff.get('changed_count', 0)} 个，"
                f"移除 {diff.get('removed_count', 0)} 个"
            )
        if json_path:
            self.log(f"当前扫描 JSON：{json_path}")
        self.maybe_prompt_auto_clean()

    def populate_overview(self):
        while self.kpi_grid.count():
            item = self.kpi_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        summary = self.scan_result.get("summary", {})
        kpis = [
            ("数据目录", self.scan_result.get("xwechat_root_size", "0 B")),
            ("可见文件", f"{summary.get('file_count', 0)} 个"),
            ("文件合计", summary.get("total_size", "0 B")),
            ("重复组", f"{summary.get('duplicate_group_count', 0)} 组"),
            ("理论重复节省", summary.get("duplicate_potential_savings", "0 B")),
            ("候选桶", f"{len(self.scan_result.get('candidates', []))} 个"),
        ]
        if self.diff_result:
            kpis.extend(
                [
                    ("新增", f"{self.diff_result.get('added_count', 0)} 个 / {self.diff_result.get('added_size', '0 B')}"),
                    ("变化", f"{self.diff_result.get('changed_count', 0)} 个"),
                    ("移除", f"{self.diff_result.get('removed_count', 0)} 个"),
                ]
            )
        for index, (label, value) in enumerate(kpis):
            box = self.panel()
            box_layout = QVBoxLayout(box)
            small = QLabel(label)
            small.setObjectName("MetricsLabel")
            big = QLabel(value)
            big.setObjectName("StatusLabel")
            box_layout.addWidget(small)
            box_layout.addWidget(big)
            self.kpi_grid.addWidget(box, index // 3, index % 3)
        rows = []
        for account in self.scan_result.get("accounts", []):
            sections = account.get("sections", {})
            biggest = next(iter(sections.items()), ("", {"size": ""}))
            rows.append([account.get("name", ""), account.get("size", ""), account.get("path", ""), f"{biggest[0]} {biggest[1].get('size', '')}"])
        self.set_rows(self.account_table, rows)

    def populate_files(self):
        if not self.scan_result:
            return
        needle = self.file_filter.text().lower() if hasattr(self, "file_filter") else ""
        rows = []
        for record in self.scan_result.get("files", []):
            text = " ".join(str(record.get(key, "")) for key in ("name", "kind", "source", "month", "path")).lower()
            if needle and needle not in text:
                continue
            rows.append(
                [
                    record.get("name", ""),
                    record.get("kind", ""),
                    record.get("source", ""),
                    record.get("month", ""),
                    record.get("size", ""),
                    record.get("path", ""),
                ]
            )
            if len(rows) >= 1000:
                break
        self.set_rows(self.file_table, rows)

    def populate_candidates(self):
        rows = []
        candidates = self.scan_result.get("candidates", []) if self.scan_result else []
        self.candidate_table.setRowCount(len(candidates))
        for row_index, candidate in enumerate(candidates):
            check = QTableWidgetItem("")
            check.setFlags(check.flags() | Qt.ItemIsUserCheckable)
            check.setCheckState(Qt.Checked)
            check.setData(Qt.UserRole, row_index)
            self.candidate_table.setItem(row_index, 0, check)
            values = [
                category_label(candidate.get("category", "")),
                candidate.get("account", ""),
                candidate.get("month", ""),
                candidate.get("size", ""),
                candidate.get("note", ""),
                candidate.get("path", ""),
            ]
            for col, value in enumerate(values, 1):
                self.candidate_table.setItem(row_index, col, QTableWidgetItem(str(value)))
        self.candidate_table.resizeColumnsToContents()

    def populate_duplicates(self):
        rows = []
        for index, group in enumerate(self.scan_result.get("duplicates", []) if self.scan_result else [], 1):
            sample = group.get("files", [{}])[0].get("path", "")
            rows.append([str(index), str(group.get("count", "")), group.get("size", ""), group.get("potential_savings", ""), sample])
        self.set_rows(self.duplicate_table, rows)

    def set_rows(self, table, rows):
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col, value in enumerate(row):
                table.setItem(row_index, col, QTableWidgetItem(str(value)))
        table.resizeColumnsToContents()

    def select_all_candidates(self):
        for row in range(self.candidate_table.rowCount()):
            item = self.candidate_table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked)

    def checked_candidates(self):
        if not self.scan_result:
            return []
        candidates = self.scan_result.get("candidates", [])
        selected = []
        for row in range(self.candidate_table.rowCount()):
            item = self.candidate_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                index = int(item.data(Qt.UserRole))
                if index < len(candidates):
                    selected.append(candidates[index])
        return selected

    def cleanup_options(self):
        try:
            min_age_days = max(0, int(self.retention_edit.text().strip()))
        except ValueError:
            min_age_days = 365
            self.retention_edit.setText("365")
        return {
            "min_age_days": min_age_days,
            "use_whitelist": self.use_whitelist_check.isChecked(),
            "whitelist_exts": [part.strip() for part in self.whitelist_exts_edit.text().split(",") if part.strip()],
            "whitelist_paths": [part.strip() for part in self.whitelist_paths_edit.text().split(",") if part.strip()],
            "categories": {
                "image": self.clean_images_check.isChecked(),
                "video": self.clean_videos_check.isChecked(),
                "file": self.clean_files_check.isChecked(),
                "cache": self.clean_cache_check.isChecked(),
            },
        }

    def preview_cleanup(self):
        if not self.scan_result:
            QMessageBox.information(self, "没有扫描结果", "请先扫描或加载历史 JSON。")
            return
        self.cleanup_plan = build_cleanup_plan(self.scan_result, options=self.cleanup_options())
        self.cleanup_label.setText(f"预览：{self.cleanup_plan['count']} 个文件 / {self.cleanup_plan['total_size']}")
        rows = []
        for index, item in enumerate(self.cleanup_plan["items"][:1000]):
            rows.append([index, item["name"], item["category_label"], item["month"], item["size"], item["path"]])
        self.cleanup_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            check = QTableWidgetItem("")
            check.setFlags(check.flags() | Qt.ItemIsUserCheckable)
            check.setCheckState(Qt.Checked)
            check.setData(Qt.UserRole, row[0])
            self.cleanup_table.setItem(row_index, 0, check)
            for col, value in enumerate(row[1:], 1):
                self.cleanup_table.setItem(row_index, col, QTableWidgetItem(str(value)))
        self.cleanup_table.resizeColumnsToContents()
        self.tabs.setCurrentIndex(3)

    def auto_state_path(self):
        return Path(self.output_edit.text()).expanduser() / "reports/macos_auto_clean_state.json"

    def load_auto_state(self):
        path = self.auto_state_path()
        if not path.exists():
            return {}
        try:
            import json

            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_auto_state(self):
        path = self.auto_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        import json

        path.write_text(json.dumps({"last_prompted_at": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=2), encoding="utf-8")

    def maybe_prompt_auto_clean(self):
        if not self.scan_result or not self.auto_clean_check.isChecked():
            return
        try:
            interval_days = max(1, int(self.auto_days_edit.text().strip()))
        except ValueError:
            interval_days = 30
            self.auto_days_edit.setText("30")
        state = self.load_auto_state()
        last_prompted = state.get("last_prompted_at", "")
        if last_prompted:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last_prompted)).days
                if elapsed < interval_days:
                    return
            except ValueError:
                pass
        result = QMessageBox.question(
            self,
            "定期自动清理",
            "已到定期清理检查周期。是否按当前类型和保留天数生成清理预览？",
        )
        self.save_auto_state()
        if result == QMessageBox.Yes:
            self.preview_cleanup()

    def selected_cleanup_paths(self):
        if not self.cleanup_plan:
            return []
        items = self.cleanup_plan.get("items", [])
        paths = []
        for row in range(self.cleanup_table.rowCount()):
            item = self.cleanup_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                index = int(item.data(Qt.UserRole))
                if index < len(items):
                    paths.append(items[index]["path"])
        return paths

    def execute_cleanup(self):
        if not self.cleanup_plan:
            self.preview_cleanup()
            if not self.cleanup_plan:
                return
        paths = self.selected_cleanup_paths()
        if not paths:
            QMessageBox.information(self, "没有选中文件", "请先勾选清理预览里的文件。")
            return
        result = QMessageBox.question(
            self,
            "确认移动到回收站",
            f"将 {len(paths)} 个文件移动到系统回收站。微信原目录会发生变化，但不是永久删除。是否继续？",
        )
        if result != QMessageBox.Yes:
            return
        self.cleanup_worker = CleanupWorker(self.cleanup_plan, paths)
        self.cleanup_worker.progress.connect(self.scan_progress)
        self.cleanup_worker.finished_ok.connect(self.cleanup_done)
        self.cleanup_worker.failed.connect(self.scan_failed)
        self.cleanup_worker.start()

    def cleanup_done(self, result):
        self.log(f"已移动到回收站：{result['moved_count']} 个 / {result['moved_size']}，失败 {result['failed_count']} 个")
        QMessageBox.information(self, "清理完成", f"已移动到回收站：{result['moved_count']} 个文件。")

    def load_scan_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择扫描 JSON", str(Path(self.output_edit.text()).expanduser()), "JSON (*.json)")
        if path:
            self.load_scan_from_path(path)

    def load_scan_from_path(self, path):
        try:
            scan = load_scan_result(path)
        except Exception as exc:  # noqa: BLE001 - shown to the user.
            QMessageBox.critical(self, "加载失败", str(exc))
            return
        self.populate_scan(scan, path)
        parent = Path(path).parent.parent
        self.output_edit.setText(str(parent))
        self.output_path = str(parent)
        self.refresh_history()
        self.tabs.setCurrentIndex(1)

    def refresh_history(self):
        output = Path(self.output_edit.text()).expanduser() if hasattr(self, "output_edit") else Path(self.output_path)
        history = load_scan_history(output)
        self.history_table.setRowCount(len(history))
        for row_index, entry in enumerate(history):
            values = [
                entry.get("generated_at", ""),
                str(entry.get("file_count", 0)),
                entry.get("total_size", ""),
                str(entry.get("diff", {}).get("added_count", "")),
                str(entry.get("diff", {}).get("changed_count", "")),
                entry.get("json", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, entry.get("json", ""))
                self.history_table.setItem(row_index, col, item)
        self.history_table.resizeColumnsToContents()

    def load_selected_history(self):
        row = self.history_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "没有选中历史", "请先在历史表中选中一条扫描。")
            return
        item = self.history_table.item(row, 0)
        path = item.data(Qt.UserRole) if item else ""
        if path:
            self.load_scan_from_path(path)

    def open_selected_file(self):
        row = self.file_table.currentRow()
        if row < 0:
            return
        path_item = self.file_table.item(row, 5)
        if path_item:
            self.open_local_path(path_item.text())

    def open_local_path(self, path):
        if not path:
            QMessageBox.information(self, "结果未生成", "请先扫描或加载结果。")
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
