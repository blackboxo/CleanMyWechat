import datetime
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import main
from utils.cleanup_rules import build_account_scan_dirs, retention_cutoff
from utils.scanThread import ScanThread


def write_file(path, modified_at):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"test")
    timestamp = modified_at.timestamp()
    os.utime(path, (timestamp, timestamp))


class CleanupScanningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "xwechat_files" / "wxid_test_123"
        self.now = datetime.datetime.now()

    def tearDown(self):
        self.tmp.cleanup()

    def test_xwechat_media_roots_follow_selected_categories(self):
        (self.root / "msg" / "attach").mkdir(parents=True)
        roots = {
            (Path(path).relative_to(self.root).as_posix(), category)
            for path, category in build_account_scan_dirs(
                self.root, False, True, True, True)
        }

        self.assertIn(("msg/attach", "image"), roots)
        self.assertIn(("msg/file", "file"), roots)
        self.assertIn(("msg/video", "video"), roots)
        self.assertNotIn(("cache", "cache"), roots)

    def test_preview_scans_nested_xwechat_files_by_exact_age(self):
        old = self.now - datetime.timedelta(days=31)
        recent = self.now - datetime.timedelta(days=29)
        old_attach = self.root / "msg" / "attach" / "chat_hash" / "2026-06" / "Img" / "old.dat"
        old_file = self.root / "msg" / "file" / "2026-06" / "old.pdf"
        old_video = self.root / "msg" / "video" / "2026-06" / "old.mp4"
        recent_video = self.root / "msg" / "video" / "2026-08" / "recent.mp4"
        for path in (old_attach, old_file, old_video):
            write_file(path, old)
        write_file(recent_video, recent)

        files = []
        dirs = []
        scanner = ScanThread({"users": []})
        scanner.get_fileNum(
            str(self.root), 30, False, True, True, True, files, dirs,
            user_config={"use_whitelist": False})

        self.assertEqual({old_attach, old_file, old_video}, {Path(path) for path in files})
        self.assertEqual([], dirs)

    def test_retention_cutoff_preserves_the_configured_number_of_days(self):
        cutoff = retention_cutoff(self.now, 30)
        self.assertEqual(self.now - datetime.timedelta(days=30), cutoff)

    def test_main_cleanup_scans_files_instead_of_deleting_month_directory(self):
        old = self.now - datetime.timedelta(days=31)
        recent = self.now - datetime.timedelta(days=29)
        old_file = self.root / "msg" / "file" / "2026-06" / "old.pdf"
        recent_file = self.root / "msg" / "file" / "2026-06" / "recent.pdf"
        write_file(old_file, old)
        write_file(recent_file, recent)

        window = main.MainWindow.__new__(main.MainWindow)
        window.keep_ui_responsive = lambda: None
        files = []
        dirs = []
        stats = window.make_empty_stats()
        user_config = {
            "clean_pic_cache": False,
            "clean_file": True,
            "clean_pic": False,
            "clean_video": False,
            "use_whitelist": False,
        }
        with patch("main.read_whitelist_file", return_value=([], [])):
            window.get_fileNum(
                str(self.root), 30, False, True, False, False,
                files, dirs, user_config=user_config, stats=stats)

        self.assertIn(str(old_file), files)
        self.assertNotIn(str(recent_file), files)
        self.assertNotIn(str(old_file.parent), dirs)
        self.assertEqual(0, stats["total_month_dirs"])

    def test_legacy_generated_document_whitelist_is_migrated(self):
        (self.root / "msg").mkdir(parents=True)
        config = {
            "data_dir": [str(self.root)],
            "users": [{
                "wechat_id": "wxid_test_123",
                "data_dir": str(self.root),
                "whitelist_exts": sorted(main.LEGACY_DEFAULT_WHITELIST_EXTS),
            }],
            "global": {},
        }

        migrated = main.ensure_config_defaults(config)

        self.assertEqual([], migrated["users"][0]["whitelist_exts"])
        self.assertEqual(2, migrated["global"]["config_schema_version"])

    def test_cleanup_summary_reports_failed_items(self):
        window = main.MainWindow.__new__(main.MainWindow)
        window.bar_progress = MagicMock()
        window.config = {"global": {"direct_delete": True}}
        window.total_file = 2
        window.total_dir = 0
        window.total_size = 1024
        window.delete_result_stats = [1, 1]
        window.thread_list = [object()]
        window.auto_clean_running = False
        window.setWarninginfo = MagicMock()
        window.setSuccessinfo = MagicMock()

        window.callback(2)

        message = window.setWarninginfo.call_args.args[0]
        self.assertIn("成功 1 个，失败 1 个", message)
        window.setSuccessinfo.assert_not_called()


if __name__ == "__main__":
    unittest.main()
