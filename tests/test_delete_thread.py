import unittest
from unittest.mock import patch

import utils.multiDeleteThread as delete_module


class DeleteThreadTest(unittest.TestCase):
    def test_default_deletion_uses_recycle_bin(self):
        thread = delete_module.multiDeleteThread(
            [r"C:\probe\old-video.mp4"], [], [0], direct_delete=False)

        with patch.object(delete_module, "send2trash") as mocked_send2trash, patch.object(
                delete_module.os, "remove") as mocked_remove:
            thread._delete_path(r"C:\probe\old-video.mp4")

        mocked_send2trash.assert_called_once_with(r"C:\probe\old-video.mp4")
        mocked_remove.assert_not_called()


if __name__ == "__main__":
    unittest.main()
