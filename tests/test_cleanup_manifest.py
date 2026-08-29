import json
import tempfile
import unittest
from pathlib import Path

from utils.cleanupManifest import cleanup_result_summary, delete_path_for_manifest, write_cleanup_manifest


def write_file(path, content=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


class CleanupManifestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_delete_records_success_skips_and_failures(self):
        ok_file = write_file(self.root / "old-video.mp4", b"video")
        protected_file = write_file(self.root / "message.db", b"sqlite")
        busy_file = write_file(self.root / "busy.tmp", b"busy")
        trashed = []

        def fake_trash(path):
            if Path(path).name == "busy.tmp":
                raise RuntimeError("file is busy")
            trashed.append(path)

        records = [
            delete_path_for_manifest(str(ok_file), "file", direct_delete=False, trash_func=fake_trash),
            delete_path_for_manifest(str(protected_file), "file", direct_delete=False, trash_func=fake_trash),
            delete_path_for_manifest(str(busy_file), "file", direct_delete=False, trash_func=fake_trash),
        ]
        result = cleanup_result_summary(records, direct_delete=False)

        by_name = {Path(row["path"]).name: row for row in result["records"]}
        self.assertEqual(by_name["old-video.mp4"]["status"], "trashed")
        self.assertEqual(by_name["message.db"]["status"], "skipped")
        self.assertEqual(by_name["message.db"]["reason"], "protected_extension")
        self.assertEqual(by_name["busy.tmp"]["status"], "failed")
        self.assertEqual(by_name["busy.tmp"]["error"], "file is busy")
        self.assertEqual(result["processed_count"], 1)
        self.assertEqual(result["skipped_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual([Path(path).name for path in trashed], ["old-video.mp4"])

    def test_write_cleanup_manifest_persists_json_summary(self):
        records = [
            {
                "path": "/tmp/old-video.mp4",
                "type": "file",
                "action": "trash",
                "status": "trashed",
                "size_bytes": 5,
                "size": "5 B",
                "error": "",
            }
        ]
        result = cleanup_result_summary(records, direct_delete=False)

        manifest_path = write_cleanup_manifest(result, self.root / "cleanup_manifests")
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["action"], "trash")
        self.assertEqual(payload["processed_count"], 1)
        self.assertEqual(payload["records"][0]["path"], "/tmp/old-video.mp4")


if __name__ == "__main__":
    unittest.main()
