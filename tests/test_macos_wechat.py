import os
import tempfile
import unittest
from pathlib import Path

from utils.macos_wechat import (
    create_symlink_view,
    discover_accounts,
    render_dashboard_html,
    scan_macos_wechat,
    write_dashboard,
)


def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


class MacOSWeChatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "xwechat_files"
        self.account = self.root / "wxid_alice_abcd"
        write_file(self.account / "msg/file/2024-01/report.pdf", b"report")
        write_file(self.account / "msg/file/2025-07/current.docx", b"current")
        write_file(self.account / "msg/video/2024-01/clip.mp4", b"video")
        write_file(self.account / "msg/attach/contact_hash/2024-01/Img/photo.jpg", b"photo")
        write_file(self.account / "cache/2024-01/cache.bin", b"cache")
        write_file(self.account / "db_storage/message/message.db", b"database")
        write_file(self.root / "all_users/config.sqlite", b"ignored")

    def tearDown(self):
        self.tmp.cleanup()

    def test_discovers_only_account_dirs(self):
        accounts = discover_accounts(self.root)
        self.assertEqual([path.name for path in accounts], ["wxid_alice_abcd"])

    def test_scan_summarizes_macos_layout(self):
        scan = scan_macos_wechat(self.root, cutoff_month="2025-01", duplicate_threshold=1024)
        self.assertTrue(scan["xwechat_root_exists"])
        self.assertEqual(len(scan["accounts"]), 1)
        self.assertEqual(scan["summary"]["file_count"], 3)
        self.assertEqual(scan["summary"]["by_kind"][0]["name"], "Word")

        categories = {(row["category"], row["month"]) for row in scan["candidates"]}
        self.assertIn(("msg_file", "2024-01"), categories)
        self.assertIn(("msg_video", "2024-01"), categories)
        self.assertIn(("msg_attach", "2024-01"), categories)
        self.assertIn(("account_cache", "2024-01"), categories)

    def test_duplicate_detection_uses_content_hash(self):
        write_file(self.account / "msg/file/2024-02/a.zip", b"same-large-enough")
        write_file(self.account / "msg/attach/hash/2024-02/Rec/a.zip", b"same-large-enough")
        write_file(self.account / "msg/file/2024-02/b.zip", b"different")

        scan = scan_macos_wechat(self.root, cutoff_month="2025-01", duplicate_threshold=1)
        self.assertEqual(scan["summary"]["duplicate_group_count"], 1)
        group = scan["duplicates"][0]
        self.assertEqual(group["count"], 2)
        self.assertGreater(group["potential_savings_bytes"], 0)

    def test_dashboard_is_self_contained(self):
        scan = scan_macos_wechat(self.root, cutoff_month="2025-01", duplicate_threshold=1024)
        html = render_dashboard_html(scan)
        self.assertIn("Clean My WeChat macOS Dashboard", html)
        self.assertIn("const DATA=", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)

        output = Path(self.tmp.name) / "dashboard.html"
        write_dashboard(scan, output)
        self.assertTrue(output.exists())

    def test_symlink_view_does_not_copy_originals(self):
        scan = scan_macos_wechat(self.root, cutoff_month="2025-01", duplicate_threshold=1024)
        output = Path(self.tmp.name) / "organized_view"
        result = create_symlink_view(scan, output)
        self.assertTrue(Path(result["readme"]).exists())
        links = [path for path in output.rglob("*") if path.is_symlink()]
        if os.name == "nt" and not links:
            self.skipTest("Symlinks are unavailable without privileges on this Windows environment.")
        self.assertTrue(links)
        report_links = [path for path in links if path.name == "report.pdf"]
        self.assertTrue(report_links)
        self.assertEqual(report_links[0].resolve().read_bytes(), b"report")


if __name__ == "__main__":
    unittest.main()
