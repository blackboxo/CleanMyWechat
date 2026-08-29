import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication, QFrame

    import main
except ModuleNotFoundError:
    Qt = None
    QApplication = None
    QFrame = None
    main = None


@unittest.skipIf(Qt is None, "PyQt5 is not installed in this interpreter")
class MacOSArchiveUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        main.configure_application(cls.app)

    def test_main_window_base_uses_native_macos_window_controls(self):
        window = main.Window()
        window.mainFrame = QFrame(window)
        window._frame()

        flags = window.windowFlags()
        if main.sys.platform == "darwin":
            self.assertFalse(bool(flags & Qt.FramelessWindowHint))
            self.assertTrue(bool(flags & Qt.WindowCloseButtonHint))
            self.assertTrue(bool(flags & Qt.WindowMinimizeButtonHint))
            self.assertTrue(bool(flags & Qt.WindowMaximizeButtonHint))

        window.close()

    def test_archive_dialog_exposes_separate_archive_and_removal_actions(self):
        with tempfile.TemporaryDirectory() as folder:
            dialog = main.ArchiveSettingsDialog(
                {
                    "archive_target": str(Path(folder) / "Archive"),
                    "archive_batch_mb": 256,
                    "archive_remove_uploaded": True,
                }
            )

            self.assertFalse(hasattr(dialog, "remove_uploaded_check"))
            self.assertEqual(dialog.batch_edit.value(), 256)
            dialog.selected_action = "archive"
            self.assertEqual(dialog.values()["action"], "archive")
            dialog.selected_action = "remove"
            self.assertEqual(dialog.values()["action"], "remove")
            dialog.close()

    def test_archive_state_path_uses_sqlite(self):
        path = main.archive_manifest_path("/tmp/CleanMyWechat Archive")
        self.assertTrue(path.endswith(".sqlite3"))

    def test_main_window_shows_native_controls_and_real_archive_button(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps({"data_dir": [], "users": [], "global": {}}),
                encoding="utf-8",
            )
            with (
                patch.object(main, "CONFIG_PATH", str(config_path)),
                patch.object(main, "WHITELIST_PATH", str(root / "whitelist.txt")),
                patch.object(main, "STATE_PATH", str(root / "state.json")),
                patch.object(main, "PREVIEW_PATH", str(root / "preview.txt")),
                patch.object(main, "ARCHIVE_STATE_DIR", str(root / "archives")),
                patch.object(main, "find_all_wechat_paths", return_value=[]),
            ):
                window = main.MainWindow()
                flags = window.windowFlags()
                self.assertTrue(hasattr(window, "btn_archive"))
                self.assertTrue(window.lab_close.isHidden())
                self.assertFalse(bool(flags & Qt.FramelessWindowHint))
                self.assertTrue(bool(flags & Qt.WindowCloseButtonHint))
                window.hide()
                window.deleteLater()
                self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
