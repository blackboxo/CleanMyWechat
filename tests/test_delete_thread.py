import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import utils.multiDeleteThread as delete_module


class DeleteThreadTest(unittest.TestCase):
    def test_default_deletion_uses_recycle_bin(self):
        thread = delete_module.multiDeleteThread(
            [r"C:\probe\old-video.mp4"], [], [0], direct_delete=False)

        with patch.object(delete_module, "send2trash") as mocked_send2trash, patch.object(
                delete_module.os, "remove") as mocked_remove:
            with patch.object(delete_module.os.path, "lexists", return_value=True), patch.object(
                    thread, "_make_writable", return_value=stat.S_IWRITE):
                succeeded = thread._delete_path(r"C:\probe\old-video.mp4")

        self.assertTrue(succeeded)
        mocked_send2trash.assert_called_once_with(r"C:\probe\old-video.mp4")
        mocked_remove.assert_not_called()

    def test_direct_delete_clears_wechat_read_only_attribute(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "old-video.mp4"
            file_path.write_bytes(b"video")
            os.chmod(file_path, stat.S_IREAD)
            thread = delete_module.multiDeleteThread(
                [str(file_path)], [], [0], direct_delete=True)

            succeeded = thread._delete_path(str(file_path))

            self.assertTrue(succeeded)
            self.assertFalse(file_path.exists())

    def test_failed_delete_restores_original_read_only_attribute(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "locked-video.mp4"
            file_path.write_bytes(b"video")
            os.chmod(file_path, stat.S_IREAD)
            thread = delete_module.multiDeleteThread(
                [str(file_path)], [], [0], direct_delete=True)

            with patch.object(delete_module.os, "remove", side_effect=PermissionError("locked")):
                succeeded = thread._delete_path(str(file_path))

            self.assertFalse(succeeded)
            self.assertTrue(file_path.exists())
            self.assertFalse(os.stat(file_path).st_mode & stat.S_IWRITE)

    def test_run_tracks_success_and_failure_separately(self):
        progress = [0]
        results = [0, 0]
        thread = delete_module.multiDeleteThread(
            ["success.mp4", "failed.mp4"], [], progress,
            direct_delete=True, result_stats=results)

        with patch.object(thread, "_delete_path", side_effect=[True, False]):
            thread.run()

        self.assertEqual([2], progress)
        self.assertEqual([1, 1], results)


if __name__ == "__main__":
    unittest.main()
