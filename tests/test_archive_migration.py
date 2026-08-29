import json
import sqlite3
import tempfile
import unittest
from collections import namedtuple
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import utils.archiveMigration as archive_migration
from utils.archiveMigration import (
    ARCHIVE_MARKER_NAME,
    SCHEMA_VERSION,
    add_sources,
    classify_file,
    get_removal_preview,
    infer_item_metadata,
    open_archive_store,
    run_archive_cycle,
    run_removal_cycle,
)


def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def local_status(_path):
    return {
        "is_icloud": False,
        "uploaded": None,
        "uploading": False,
        "upload_error": None,
        "status_error": None,
    }


def waiting_status(_path):
    return {
        "is_icloud": True,
        "uploaded": False,
        "uploading": True,
        "upload_error": None,
        "status_error": None,
    }


def uploaded_status(_path):
    return {
        "is_icloud": True,
        "uploaded": True,
        "uploading": False,
        "upload_error": None,
        "status_error": None,
    }


class ArchiveMigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.account = self.root / "xwechat_files" / "wxid_alice"
        self.archive = self.root / "iCloud Archive"
        self.database_path = self.root / "state" / "archive.sqlite3"

    def tearDown(self):
        self.tmp.cleanup()

    def source(self, path, category=None):
        return {
            "path": str(path),
            "account_root": str(self.account),
            "account_id": "wxid_alice",
            "category": category,
        }

    def database_item(self, source):
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                "SELECT * FROM items WHERE source = ?",
                (str(Path(source).resolve()),),
            ).fetchone()

    def archived_files(self):
        return [
            path
            for path in self.archive.rglob("*")
            if path.is_file() and path.name != ARCHIVE_MARKER_NAME
        ]

    def archive_locally(self, sources, batch_bytes=1024):
        return run_archive_cycle(
            self.database_path,
            self.archive,
            sources,
            batch_bytes=batch_bytes,
            upload_checker=local_status,
        )

    def trash_by_unlinking(self, path):
        Path(path).unlink()

    def test_infers_month_conversation_and_type(self):
        photo = write_file(
            self.account / "msg/attach/contact_hash/2024-03/Img/photo.jpg",
            b"photo",
        )

        metadata = infer_item_metadata(
            photo,
            self.account,
            account_id="wxid_alice",
        )

        self.assertEqual(metadata["year"], "2024")
        self.assertEqual(metadata["month"], "2024-03")
        self.assertEqual(metadata["conversation"], "contact_hash")
        self.assertEqual(metadata["kind"], "image")

    def test_ancestor_tmp_directory_does_not_force_cache_classification(self):
        account_root = Path("/tmp/trial/xwechat_files/wxid_alice")
        image = account_root / "msg/attach/contact_hash/2024-03/Img/photo.jpg"

        self.assertEqual(
            classify_file(image, account_root=account_root),
            "image",
        )

    def test_archive_cycle_deduplicates_but_never_removes_sources(self):
        first = write_file(
            self.account / "msg/attach/contact_a/2024-01/report.pdf",
            b"same-content",
        )
        second = write_file(
            self.account / "msg/file/2024-01/report-copy.pdf",
            b"same-content",
        )

        result = self.archive_locally(
            [self.source(first), self.source(second)],
        )

        self.assertEqual(len(self.archived_files()), 1)
        self.assertEqual(result["batch"]["duplicates"], 1)
        self.assertEqual(result["removal"]["removed"], 0)
        self.assertEqual(result["summary"]["ready_to_remove"], 2)
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())

    def test_removal_requires_a_separate_confirmation(self):
        source = write_file(
            self.account / "msg/file/2024-01/notes.txt",
            b"content",
        )
        self.archive_locally([self.source(source)])

        with self.assertRaisesRegex(PermissionError, "单独确认"):
            run_removal_cycle(
                self.database_path,
                self.archive,
                confirmed=False,
                trash_func=self.trash_by_unlinking,
            )

        result = run_removal_cycle(
            self.database_path,
            self.archive,
            confirmed=True,
            trash_func=self.trash_by_unlinking,
        )

        self.assertEqual(result["removal"]["removed"], 1)
        self.assertFalse(source.exists())

    def test_icloud_waiting_state_keeps_source_until_later_cleanup(self):
        video = write_file(
            self.account / "msg/video/2024-02/clip.mp4",
            b"video-content",
        )

        first = run_archive_cycle(
            self.database_path,
            self.archive,
            [self.source(video, "video")],
            batch_bytes=1024,
            upload_checker=waiting_status,
        )

        self.assertEqual(first["summary"]["awaiting_upload"], 1)
        self.assertTrue(video.exists())

        second = run_archive_cycle(
            self.database_path,
            self.archive,
            [self.source(video, "video")],
            batch_bytes=1024,
            upload_checker=uploaded_status,
        )

        self.assertEqual(second["batch"]["copied"], 0)
        self.assertEqual(second["summary"]["ready_to_remove"], 1)
        self.assertTrue(video.exists())

        removal = run_removal_cycle(
            self.database_path,
            self.archive,
            confirmed=True,
            trash_func=self.trash_by_unlinking,
        )
        self.assertEqual(removal["removal"]["removed"], 1)
        self.assertFalse(video.exists())

    def test_changed_source_is_never_removed(self):
        document = write_file(
            self.account / "msg/file/2024-04/notes.txt",
            b"original",
        )
        self.archive_locally([self.source(document)])
        document.write_bytes(b"changed-after-copy")

        result = run_removal_cycle(
            self.database_path,
            self.archive,
            confirmed=True,
            trash_func=self.trash_by_unlinking,
        )

        self.assertEqual(result["removal"]["changed"], 1)
        self.assertTrue(document.exists())
        self.assertEqual(self.database_item(document)["status"], "source_changed")

    def test_source_changing_during_final_hash_is_never_removed(self):
        document = write_file(
            self.account / "msg/file/2024-04/changing.txt",
            b"original",
        )
        self.archive_locally([self.source(document)])
        original_sha256_file = archive_migration.sha256_file

        def mutate_after_hash(path, *args, **kwargs):
            digest = original_sha256_file(path, *args, **kwargs)
            if (
                Path(path).resolve() == document.resolve()
                and document.read_bytes() == b"original"
            ):
                document.write_bytes(b"changed-during-hash")
            return digest

        with patch.object(
            archive_migration,
            "sha256_file",
            side_effect=mutate_after_hash,
        ):
            result = run_removal_cycle(
                self.database_path,
                self.archive,
                confirmed=True,
                trash_func=self.trash_by_unlinking,
            )

        self.assertEqual(result["removal"]["failed"], 1)
        self.assertTrue(document.exists())
        self.assertEqual(self.database_item(document)["status"], "removal_failed")

    def test_trash_callback_must_actually_remove_source(self):
        document = write_file(
            self.account / "msg/file/2024-04/keep.txt",
            b"content",
        )
        self.archive_locally([self.source(document)])

        result = run_removal_cycle(
            self.database_path,
            self.archive,
            confirmed=True,
            trash_func=lambda _path: None,
        )

        self.assertEqual(result["removal"]["failed"], 1)
        self.assertTrue(document.exists())
        self.assertEqual(self.database_item(document)["status"], "removal_failed")

        self.archive_locally([self.source(document)])
        retry = run_removal_cycle(
            self.database_path,
            self.archive,
            confirmed=True,
            trash_func=self.trash_by_unlinking,
        )
        self.assertEqual(retry["removal"]["removed"], 1)

    def test_trash_adapter_error_after_move_is_recorded_as_unconfirmed(self):
        document = write_file(
            self.account / "msg/file/2024-04/moved-then-error.txt",
            b"content",
        )
        self.archive_locally([self.source(document)])

        def move_then_raise(path):
            Path(path).unlink()
            raise RuntimeError("synthetic adapter error")

        result = run_removal_cycle(
            self.database_path,
            self.archive,
            confirmed=True,
            trash_func=move_then_raise,
        )

        self.assertEqual(result["removal"]["unconfirmed"], 1)
        self.assertEqual(
            self.database_item(document)["status"],
            "removed_unconfirmed",
        )

    def test_batch_limit_processes_at_least_one_file_and_resumes(self):
        files = [
            write_file(
                self.account / f"msg/file/2024-05/file-{index}.bin",
                b"x" * 6,
            )
            for index in range(3)
        ]
        sources = [self.source(path) for path in files]

        first = self.archive_locally(sources, batch_bytes=10)
        second = self.archive_locally(sources, batch_bytes=10)
        third = self.archive_locally(sources, batch_bytes=10)

        self.assertEqual(first["batch"]["selected"], 1)
        self.assertEqual(second["batch"]["selected"], 1)
        self.assertEqual(third["batch"]["selected"], 1)
        self.assertEqual(len(self.archived_files()), 1)
        self.assertEqual(third["summary"]["ready_to_remove"], 3)

    def test_same_name_different_content_gets_collision_suffix(self):
        first = write_file(
            self.account / "msg/file/2024-06/a/report.bin",
            b"first",
        )
        second = write_file(
            self.account / "msg/file/2024-06/b/report.bin",
            b"second",
        )

        self.archive_locally([self.source(first), self.source(second)])

        names = sorted(path.name for path in self.archive.rglob("report*"))
        self.assertEqual(len(names), 2)
        self.assertIn("report.bin", names)
        self.assertTrue(any(name.startswith("report__") for name in names))

    def test_existing_hash_suffix_path_is_never_overwritten(self):
        first = write_file(
            self.account / "msg/file/2024-06/a/report.bin",
            b"first",
        )
        second = write_file(
            self.account / "msg/file/2024-06/b/report.bin",
            b"second",
        )
        self.archive_locally([self.source(first)])
        canonical = next(self.archive.rglob("report.bin"))
        second_digest = archive_migration.sha256_file(second)
        occupied = canonical.with_name(f"report__{second_digest[:10]}.bin")
        occupied.write_bytes(b"unrelated-archive-content")

        result = self.archive_locally([self.source(second)])

        self.assertEqual(result["batch"]["failed"], 1)
        self.assertEqual(occupied.read_bytes(), b"unrelated-archive-content")
        self.assertTrue(second.exists())

    def test_new_duplicate_reuses_canonical_after_original_was_removed(self):
        original = write_file(
            self.account / "msg/file/2024-06/original.bin",
            b"shared",
        )
        self.archive_locally([self.source(original)])
        run_removal_cycle(
            self.database_path,
            self.archive,
            confirmed=True,
            trash_func=self.trash_by_unlinking,
        )
        later = write_file(
            self.account / "msg/attach/contact/2024-07/later.bin",
            b"shared",
        )

        result = self.archive_locally([self.source(later)])

        self.assertEqual(result["batch"]["duplicates"], 1)
        self.assertTrue(later.exists())
        self.assertEqual(len(self.archived_files()), 1)

    def test_directory_expansion_skips_protected_database(self):
        folder = self.account / "msg/attach/contact/2024-07"
        kept = write_file(folder / "data.db", b"database")
        archived = write_file(folder / "photo.png", b"image")

        with open_archive_store(
            self.database_path,
            self.archive,
            batch_bytes=1024,
        ) as store:
            result = add_sources(store, [self.source(folder)])
            items = store.connection.execute("SELECT source FROM items").fetchall()
            skipped = store.connection.execute("SELECT source FROM skipped").fetchall()

        self.assertEqual(result["added"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(items[0]["source"], str(archived.resolve()))
        self.assertEqual(skipped[0]["source"], str(kept.resolve()))

    def test_rejects_archive_target_inside_wechat_tree(self):
        source = write_file(
            self.account / "msg/file/2024-08/file.txt",
            b"content",
        )
        inside_archive = self.account / "Archive"

        with (
            open_archive_store(
                self.database_path,
                inside_archive,
                batch_bytes=1024,
            ) as store,
            self.assertRaisesRegex(
                ValueError,
                "归档目标不能放在微信数据目录内部",
            ),
        ):
            add_sources(store, [self.source(source)])

    def test_state_is_sqlite_and_integrity_check_passes(self):
        source = write_file(
            self.account / "msg/file/2024-09/file.txt",
            b"content",
        )
        self.archive_locally([self.source(source)])

        with closing(sqlite3.connect(self.database_path)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            schema = connection.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()[0]

        self.assertEqual(integrity, "ok")
        self.assertEqual(int(schema), SCHEMA_VERSION)
        self.assertFalse(Path(str(self.database_path) + ".tmp").exists())

    def test_low_free_space_blocks_copy_and_keeps_source(self):
        source = write_file(
            self.account / "msg/file/2024-09/large.bin",
            b"x" * 1024,
        )
        DiskUsage = namedtuple("DiskUsage", "total used free")

        with patch.object(
            archive_migration.shutil,
            "disk_usage",
            return_value=DiskUsage(1024, 1023, 1),
        ):
            result = self.archive_locally([self.source(source)])

        self.assertEqual(result["batch"]["failed"], 1)
        self.assertTrue(source.exists())
        self.assertEqual(self.database_item(source)["status"], "failed")
        self.assertIn("安全余量", self.database_item(source)["error"])

    def test_low_state_disk_space_blocks_removal_before_trash(self):
        source = write_file(
            self.account / "msg/file/2024-09/remove-later.bin",
            b"content",
        )
        self.archive_locally([self.source(source)])
        DiskUsage = namedtuple("DiskUsage", "total used free")

        with (
            patch.object(
                archive_migration.shutil,
                "disk_usage",
                return_value=DiskUsage(1024, 1023, 1),
            ),
            self.assertRaisesRegex(OSError, "状态库可用空间不足"),
        ):
            run_removal_cycle(
                self.database_path,
                self.archive,
                confirmed=True,
                trash_func=self.trash_by_unlinking,
            )

        self.assertTrue(source.exists())
        self.assertEqual(self.database_item(source)["status"], "ready_to_remove")

    def test_missing_archive_root_blocks_cleanup(self):
        source = write_file(
            self.account / "msg/file/2024-10/file.txt",
            b"content",
        )
        self.archive_locally([self.source(source)])
        moved_archive = self.root / "archive-moved-for-test"
        self.archive.rename(moved_archive)

        with self.assertRaisesRegex(FileNotFoundError, "归档文件夹不存在"):
            get_removal_preview(self.database_path, self.archive)

        self.assertTrue(source.exists())

    def test_marker_mismatch_blocks_cleanup(self):
        source = write_file(
            self.account / "msg/file/2024-10/file.txt",
            b"content",
        )
        self.archive_locally([self.source(source)])
        marker_path = self.archive / ARCHIVE_MARKER_NAME
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["archive_id"] = "another-archive"
        marker_path.write_text(json.dumps(marker), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "不匹配"):
            run_removal_cycle(
                self.database_path,
                self.archive,
                confirmed=True,
                trash_func=self.trash_by_unlinking,
            )

        self.assertTrue(source.exists())

    def test_legacy_json_import_never_grants_cleanup_authority(self):
        source = write_file(
            self.account / "msg/file/2024-11/file.txt",
            b"content",
        )
        legacy_path = self.database_path.with_suffix(".json")
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "archive_root": str(self.archive.resolve()),
                    "items": [
                        {
                            "source": str(source.resolve()),
                            "account_root": str(self.account.resolve()),
                            "account": "wxid_alice",
                            "conversation": "contact",
                            "year": "2024",
                            "month": "2024-11",
                            "kind": "document",
                            "size": source.stat().st_size,
                            "mtime_ns": source.stat().st_mtime_ns,
                            "status": "ready_to_remove",
                            "sha256": archive_migration.sha256_file(source),
                            "archive_relative": "2024/2024-11/file.txt",
                            "duplicate_of": None,
                            "upload_state": "uploaded",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        with open_archive_store(
            self.database_path,
            self.archive,
            batch_bytes=1024,
        ) as store:
            row = store.item(source.resolve())
            imported_from = store.get_meta("legacy_imported_from")

        self.assertEqual(row["status"], "legacy_verification_required")
        self.assertEqual(imported_from, str(legacy_path))
        self.assertTrue(legacy_path.exists())
        with self.assertRaisesRegex(FileNotFoundError, "归档文件夹不存在"):
            run_removal_cycle(
                self.database_path,
                self.archive,
                confirmed=True,
                trash_func=self.trash_by_unlinking,
            )
        self.assertTrue(source.exists())

    def test_interrupted_removal_is_reconciled_conservatively(self):
        source = write_file(
            self.account / "msg/file/2024-12/file.txt",
            b"content",
        )
        self.archive_locally([self.source(source)])

        with open_archive_store(self.database_path, self.archive) as store:
            store.update_item(source.resolve(), status="removing")
        with open_archive_store(self.database_path, self.archive) as store:
            self.assertEqual(store.item(source.resolve())["status"], "ready_to_remove")
            store.update_item(source.resolve(), status="removing")
        source.unlink()
        with open_archive_store(self.database_path, self.archive) as store:
            row = store.item(source.resolve())

        self.assertEqual(row["status"], "removed_unconfirmed")
        self.assertIn("无法确认", row["error"])

    def test_removal_batch_is_bounded_by_item_count(self):
        files = [
            write_file(
                self.account / f"msg/file/2025-01/file-{index}.txt",
                f"content-{index}".encode(),
            )
            for index in range(5)
        ]
        self.archive_locally(
            [self.source(path) for path in files],
            batch_bytes=1024 * 1024,
        )

        result = run_removal_cycle(
            self.database_path,
            self.archive,
            confirmed=True,
            max_items=2,
            max_bytes=1024 * 1024,
            trash_func=self.trash_by_unlinking,
        )

        self.assertEqual(result["removal"]["selected"], 2)
        self.assertEqual(result["removal"]["removed"], 2)
        self.assertEqual(sum(path.exists() for path in files), 3)

    def test_sqlite_handles_seventy_five_thousand_rows_without_json_rewrites(self):
        total_rows = 75_000
        now = archive_migration.utc_now()
        with open_archive_store(
            self.database_path,
            self.archive,
            batch_bytes=1024,
            migrate_legacy=False,
        ) as store:
            rows = (
                (
                    f"/synthetic/wxid/account/msg/file/{index}.bin",
                    "/synthetic/wxid/account",
                    "wxid_scale",
                    "unknown_conversation",
                    "2025",
                    "2025-01",
                    "file",
                    index % 4096,
                    index,
                    "pending",
                    "not_checked",
                    now,
                    now,
                )
                for index in range(total_rows)
            )
            with store.connection:
                store.connection.executemany(
                    """
                    INSERT INTO items(
                        source, account_root, account, conversation, year, month,
                        kind, size, mtime_ns, status, upload_state,
                        created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            store.update_item(
                "/synthetic/wxid/account/msg/file/74999.bin",
                status="failed",
                error="synthetic update",
            )
            store.checkpoint()
            count = store.connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
            integrity = store.connection.execute("PRAGMA integrity_check").fetchone()[0]

        self.assertEqual(count, total_rows)
        self.assertEqual(integrity, "ok")
        self.assertLess(self.database_path.stat().st_size, 80 * 1024 * 1024)
        self.assertFalse(Path(str(self.database_path) + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
