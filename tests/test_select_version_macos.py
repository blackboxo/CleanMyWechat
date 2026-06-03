import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.selectVersion import check_dir, find_all_wechat_paths, get_dir_name


def write_file(path, content=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class SelectVersionMacOSTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_macos_xwechat_account_root(self):
        xwechat_root = self.root / "xwechat_files"
        write_file(xwechat_root / "wxid_alice/msg/file/2024-01/report.pdf")

        self.assertEqual(check_dir(str(xwechat_root)), 0)
        dirs, names = get_dir_name(str(xwechat_root))

        self.assertEqual([Path(path).name for path in dirs], ["wxid_alice"])
        self.assertEqual(names, ["wxid_alice"])

    def test_detects_macos_wxwork_users_root(self):
        users_root = self.root / "WXWork/Users"
        write_file(users_root / "user_123/Data/File/2024-01/report.pdf")

        self.assertEqual(check_dir(str(users_root)), 0)
        dirs, names = get_dir_name(str(users_root))

        self.assertEqual([Path(path).name for path in dirs], ["user_123"])
        self.assertEqual(names, ["WXWork-user_123"])

    def test_find_all_wechat_paths_includes_macos_candidates(self):
        xwechat_root = self.root / "xwechat_files"
        write_file(xwechat_root / "wxid_alice/msg/file/2024-01/report.pdf")

        with patch("utils.selectVersion.os.name", "posix"), patch(
            "utils.selectVersion.macos_wechat_candidates",
            return_value=[str(xwechat_root)],
        ):
            paths = find_all_wechat_paths()

        self.assertIn(str(xwechat_root), paths)


if __name__ == "__main__":
    unittest.main()
