import sys
import traceback
from pathlib import Path

from PyQt5.QtCore import QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
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
    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, source, output, cutoff_month):
        super().__init__()
        self.source = Path(source).expanduser()
        self.output = Path(output).expanduser()
        self.cutoff_month = cutoff_month

    def run(self):
        try:
            self.message.emit("Scanning macOS WeChat files...")
            scan = scan_macos_wechat(self.source, cutoff_month=self.cutoff_month)

            reports_dir = self.output / "reports"
            dashboard_path = self.output / "dashboard/wechat_dashboard.html"
            summary_path = reports_dir / "macos_wechat_summary.md"
            view_dir = self.output / "organized_view"

            self.message.emit("Writing reports and dashboard...")
            outputs = write_scan_outputs(scan, reports_dir)
            write_markdown_summary(scan, summary_path)
            write_dashboard(scan, dashboard_path)

            self.message.emit("Creating symlink organized view...")
            view_result = create_symlink_view(scan, view_dir)

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
        self.setWindowTitle("Clean My WeChat macOS")
        self.resize(920, 640)
        self.setMinimumSize(820, 560)
        self.build_ui()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("Clean My WeChat macOS")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)

        subtitle = QLabel("Read-only scanner, statistics dashboard, duplicate review, and symlink organization for macOS WeChat.")
        subtitle.setStyleSheet("color: #5f6975;")
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        layout.addLayout(grid)

        self.source_edit = QLineEdit(str(default_xwechat_root()))
        self.output_edit = QLineEdit(self.output_path)
        self.cutoff_edit = QLineEdit(DEFAULT_CUTOFF_MONTH)
        self.cutoff_edit.setMaximumWidth(120)

        grid.addWidget(QLabel("xwechat_files"), 0, 0)
        grid.addWidget(self.source_edit, 0, 1)
        source_button = QPushButton("Choose")
        source_button.clicked.connect(self.choose_source)
        grid.addWidget(source_button, 0, 2)

        grid.addWidget(QLabel("Output"), 1, 0)
        grid.addWidget(self.output_edit, 1, 1)
        output_button = QPushButton("Choose")
        output_button.clicked.connect(self.choose_output)
        grid.addWidget(output_button, 1, 2)

        grid.addWidget(QLabel("Candidate cutoff"), 2, 0)
        grid.addWidget(self.cutoff_edit, 2, 1)

        actions = QHBoxLayout()
        layout.addLayout(actions)
        self.scan_button = QPushButton("Scan and Build Dashboard")
        self.scan_button.clicked.connect(self.run_scan)
        actions.addWidget(self.scan_button)

        open_dashboard = QPushButton("Open Dashboard")
        open_dashboard.clicked.connect(self.open_dashboard)
        actions.addWidget(open_dashboard)

        open_view = QPushButton("Open Organized View")
        open_view.clicked.connect(self.open_view)
        actions.addWidget(open_view)

        actions.addStretch(1)
        open_output = QPushButton("Open Output Folder")
        open_output.clicked.connect(self.open_output)
        actions.addWidget(open_output)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background: #fbfcfd;")
        layout.addWidget(self.log_area, 1)

        self.log("Ready. This app does not move, delete, or rename WeChat files.")
        self.log(f"Default source: {self.source_edit.text()}")

    def log(self, text):
        self.log_area.append(text)

    def choose_source(self):
        path = QFileDialog.getExistingDirectory(self, "Choose xwechat_files folder", self.source_edit.text())
        if path:
            self.source_edit.setText(path)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_edit.text())
        if path:
            self.output_edit.setText(path)

    def run_scan(self):
        source = Path(self.source_edit.text()).expanduser()
        output = Path(self.output_edit.text()).expanduser()
        cutoff = self.cutoff_edit.text().strip()
        if len(cutoff) != 7 or cutoff[4] != "-":
            QMessageBox.warning(self, "Invalid cutoff", "Use YYYY-MM, for example 2025-06.")
            return
        if not source.exists():
            QMessageBox.warning(self, "Missing source", f"Source folder does not exist:\n{source}")
            return

        self.scan_button.setEnabled(False)
        self.output_path = str(output)
        self.worker = ScanWorker(source, output, cutoff)
        self.worker.message.connect(self.log)
        self.worker.finished_ok.connect(self.scan_done)
        self.worker.failed.connect(self.scan_failed)
        self.worker.start()

    def scan_done(self, result):
        self.scan_button.setEnabled(True)
        self.dashboard_path = result["dashboard"]
        self.view_path = result["view"]
        self.log(f"Accounts: {result['accounts']}")
        self.log(f"Visible files: {result['files']} / {result['visible_size']}")
        self.log(f"Duplicate groups: {result['duplicates']} / {result['duplicate_savings']}")
        self.log(f"Dashboard: {result['dashboard']}")
        self.log(f"Organized view: {result['view']}")
        self.log(f"Summary: {result['summary']}")
        self.log(f"JSON: {result['json']}")
        QMessageBox.information(self, "Dashboard ready", "The macOS WeChat dashboard has been generated.")

    def scan_failed(self, details):
        self.scan_button.setEnabled(True)
        self.log(details)
        QMessageBox.critical(self, "Scan failed", details)

    def open_local_path(self, path):
        if not path:
            QMessageBox.information(self, "Not ready", "Run Scan and Build Dashboard first.")
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
