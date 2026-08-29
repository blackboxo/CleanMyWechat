import errno
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import unicodedata
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

try:
    from send2trash import send2trash as _send2trash
except ImportError:

    def _send2trash(_path):
        raise RuntimeError("缺少 Send2Trash，无法安全移动源文件到废纸篓")


SCHEMA_VERSION = 2
DEFAULT_BATCH_BYTES = 512 * 1024 * 1024
DEFAULT_BATCH_ITEMS = 5000
DEFAULT_UPLOAD_CHECK_ITEMS = 5000
DEFAULT_REMOVAL_ITEMS = 200
DEFAULT_REMOVAL_BYTES = 512 * 1024 * 1024
MIN_FREE_SPACE_RESERVE = 512 * 1024 * 1024
MIN_STATE_FREE_SPACE_RESERVE = 64 * 1024 * 1024
COPY_CHUNK_BYTES = 4 * 1024 * 1024
MONTH_PATTERN = re.compile(r"^(?P<year>20\d{2})-(?P<month>0[1-9]|1[0-2])$")
ARCHIVE_MARKER_NAME = ".cleanmywechat-archive.json"

PROTECTED_EXTS = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-shm",
    ".db-wal",
    ".ldb",
    ".sst",
    ".dll",
    ".exe",
    ".msi",
    ".sys",
    ".ocx",
    ".pyd",
    ".so",
    ".dylib",
    ".bat",
    ".cmd",
    ".ps1",
    ".vbs",
    ".js",
    ".jar",
    ".pak",
}

IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
    ".heic",
    ".dat",
}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".m4v", ".3gp"}
AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".amr", ".silk"}
DOCUMENT_EXTS = {
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".pdf",
    ".txt",
    ".csv",
    ".rtf",
    ".pages",
    ".numbers",
    ".key",
}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}
CACHE_EXTS = {".cache", ".tmp", ".temp", ".log", ".old"}

KIND_LABELS = {
    "image": "images",
    "video": "videos",
    "audio": "audio",
    "document": "documents",
    "archive": "archives",
    "cache": "cache",
    "file": "files",
    "other": "other",
}

JXA_ICLOUD_STATUS = r"""
function run(argv) {
    ObjC.import("Foundation");
    function readFlag(target, key) {
        var value = Ref();
        var error = Ref();
        var ok = target.getResourceValueForKeyError(value, key, error);
        if (!ok) {
            return null;
        }
        return value[0] ? Boolean(value[0].boolValue) : null;
    }
    function statusForPath(path) {
        var url = $.NSURL.fileURLWithPath($(path).stringByStandardizingPath);
        var containerIsICloud = false;
        var parent = url.URLByDeletingLastPathComponent;
        for (var index = 0; index < 12 && parent; index++) {
            if (readFlag(parent, $.NSURLIsUbiquitousItemKey) === true) {
                containerIsICloud = true;
                break;
            }
            var nextParent = parent.URLByDeletingLastPathComponent;
            if (!nextParent || ObjC.unwrap(nextParent.path) === ObjC.unwrap(parent.path)) {
                break;
            }
            parent = nextParent;
        }
        var errorValue = Ref();
        var errorError = Ref();
        var errorOk = url.getResourceValueForKeyError(
            errorValue,
            $.NSURLUbiquitousItemUploadingErrorKey,
            errorError
        );
        var uploadError = null;
        if (errorOk && errorValue[0]) {
            uploadError = ObjC.unwrap(errorValue[0].localizedDescription);
        }
        return {
            path: String(path),
            is_icloud: readFlag(url, $.NSURLIsUbiquitousItemKey),
            container_is_icloud: containerIsICloud,
            uploaded: readFlag(url, $.NSURLUbiquitousItemIsUploadedKey),
            uploading: readFlag(url, $.NSURLUbiquitousItemIsUploadingKey),
            upload_error: uploadError
        };
    }
    return JSON.stringify(argv.map(statusForPath));
}
"""


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolved(path):
    return Path(path).expanduser().resolve(strict=False)


def _is_relative_to(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def is_probable_icloud_path(path):
    if sys.platform != "darwin":
        return False
    cloud_docs = _resolved(
        Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    )
    return _is_relative_to(_resolved(path), cloud_docs)


def _unavailable_icloud_status(path, error):
    probable_icloud = is_probable_icloud_path(path)
    return {
        "is_icloud": True if probable_icloud else None,
        "uploaded": None,
        "uploading": None,
        "upload_error": None,
        "status_error": str(error),
    }


def _normalize_icloud_status(path, result):
    target = _resolved(path)
    probable_icloud = is_probable_icloud_path(target)
    resource_is_icloud = result.get("is_icloud")
    if (
        probable_icloud or result.get("container_is_icloud") is True
    ) and resource_is_icloud is not True:
        result["is_icloud"] = True
        result["uploaded"] = False
    result["status_error"] = None
    return result


def query_icloud_statuses(paths, timeout=30, chunk_size=100):
    """Return conservative iCloud states with one Foundation call per chunk."""
    targets = [_resolved(path) for path in paths]
    if sys.platform != "darwin":
        return {
            str(target): {
                "is_icloud": False,
                "uploaded": None,
                "uploading": False,
                "upload_error": None,
                "status_error": None,
            }
            for target in targets
        }
    states = {}
    width = max(int(chunk_size), 1)
    for offset in range(0, len(targets), width):
        chunk = targets[offset : offset + width]
        command = [
            "/usr/bin/osascript",
            "-l",
            "JavaScript",
            "-e",
            JXA_ICLOUD_STATUS,
            "--",
        ] + [str(target) for target in chunk]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or "osascript failed")
            raw_results = json.loads(completed.stdout.strip())
            if not isinstance(raw_results, list) or len(raw_results) != len(chunk):
                raise ValueError("iCloud 状态返回数量不匹配")
            for target, result in zip(chunk, raw_results):
                states[str(target)] = _normalize_icloud_status(target, result)
        except Exception as exc:  # noqa: BLE001 - unavailable status must stay non-destructive
            for target in chunk:
                states[str(target)] = _unavailable_icloud_status(target, exc)
    return states


def query_icloud_status(path, timeout=15):
    target = _resolved(path)
    return query_icloud_statuses([target], timeout=timeout)[str(target)]


def _atomic_write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


@contextmanager
def archive_lock(path):
    lock_path = Path(path).with_name(Path(path).name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as handle:
        try:
            if os.name == "posix":
                import fcntl

                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise RuntimeError("另一个归档任务正在使用这份本地状态库") from exc
            yield
        finally:
            if os.name == "posix":
                try:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass


class ArchiveStore:
    """Small transactional updates replace the old whole-manifest JSON rewrite."""

    def __init__(self, path, archive_root, batch_bytes=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.archive_root = _resolved(archive_root)
        self.connection = sqlite3.connect(str(self.path), timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._create_schema()
        self._configure(batch_bytes)

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()

    def _create_schema(self):
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS items (
                    source TEXT PRIMARY KEY,
                    account_root TEXT NOT NULL,
                    account TEXT NOT NULL,
                    conversation TEXT NOT NULL,
                    year TEXT NOT NULL,
                    month TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    sha256 TEXT,
                    archive_relative TEXT,
                    duplicate_of TEXT,
                    upload_state TEXT NOT NULL DEFAULT 'not_checked',
                    icloud_status_json TEXT,
                    error TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    removed_at TEXT,
                    removal_started_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_items_status
                    ON items(status);
                CREATE INDEX IF NOT EXISTS idx_items_sha256
                    ON items(sha256);
                CREATE INDEX IF NOT EXISTS idx_items_duplicate
                    ON items(duplicate_of);

                CREATE TABLE IF NOT EXISTS skipped (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _configure(self, batch_bytes):
        schema_version = self.get_meta("schema_version")
        if schema_version is not None and int(schema_version) != SCHEMA_VERSION:
            raise ValueError("不支持的归档状态库版本")
        existing_root = self.get_meta("archive_root")
        if existing_root is not None and _resolved(existing_root) != self.archive_root:
            raise ValueError("归档状态库对应另一个目标文件夹")
        with self.connection:
            self.set_meta("schema_version", str(SCHEMA_VERSION))
            self.set_meta("archive_root", str(self.archive_root))
            if batch_bytes is not None or self.get_meta("batch_bytes") is None:
                configured_batch = (
                    DEFAULT_BATCH_BYTES if batch_bytes is None else batch_bytes
                )
                self.set_meta("batch_bytes", str(max(int(configured_batch), 1)))
            if self.get_meta("archive_id") is None:
                self.set_meta("archive_id", str(uuid.uuid4()))
            if self.get_meta("created_at") is None:
                self.set_meta("created_at", utc_now())
            self.set_meta("updated_at", utc_now())

    def get_meta(self, key, default=None):
        row = self.connection.execute(
            "SELECT value FROM meta WHERE key = ?",
            (key,),
        ).fetchone()
        return row["value"] if row is not None else default

    def set_meta(self, key, value):
        self.connection.execute(
            """
            INSERT INTO meta(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, str(value)),
        )

    @property
    def archive_id(self):
        return self.get_meta("archive_id")

    @property
    def batch_bytes(self):
        return max(int(self.get_meta("batch_bytes", DEFAULT_BATCH_BYTES)), 1)

    def item(self, source):
        return self.connection.execute(
            "SELECT * FROM items WHERE source = ?",
            (str(source),),
        ).fetchone()

    def items_with_status(self, statuses):
        placeholders = ",".join("?" for _ in statuses)
        return self.connection.execute(
            f"SELECT * FROM items WHERE status IN ({placeholders}) ORDER BY rowid",
            tuple(statuses),
        ).fetchall()

    def update_item(self, source, **values):
        if not values:
            return
        values["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in values)
        parameters = list(values.values()) + [str(source)]
        with self.connection:
            self.connection.execute(
                f"UPDATE items SET {assignments} WHERE source = ?",
                parameters,
            )
            self.set_meta("updated_at", utc_now())

    def checkpoint(self):
        self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def count_archived_records(self):
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM items
            WHERE archive_relative IS NOT NULL
            """
        ).fetchone()
        return int(row["count"])

    def reconcile_interrupted(self):
        with self.connection:
            self.connection.execute(
                """
                UPDATE items
                SET status = 'pending',
                    error = '上次归档在写入状态前中断，已安排重新校验',
                    updated_at = ?
                WHERE status = 'archiving'
                """,
                (utc_now(),),
            )
        rows = self.items_with_status(("removing",))
        for row in rows:
            source = Path(row["source"])
            if source.exists():
                self.update_item(
                    row["source"],
                    status="ready_to_remove",
                    removal_started_at=None,
                    error="上次清理在移入废纸篓前中断，源文件仍在",
                )
            else:
                self.update_item(
                    row["source"],
                    status="removed_unconfirmed",
                    error="上次清理中断后源路径已不存在，无法确认移除结果",
                )

    def summary(self):
        rows = self.connection.execute(
            "SELECT status, COUNT(*) AS count FROM items GROUP BY status"
        ).fetchall()
        statuses = Counter({row["status"]: int(row["count"]) for row in rows})
        unique_row = self.connection.execute(
            """
            SELECT COUNT(DISTINCT sha256) AS count
            FROM items
            WHERE sha256 IS NOT NULL AND archive_relative IS NOT NULL
            """
        ).fetchone()
        duplicate_row = self.connection.execute(
            """
            SELECT COALESCE(SUM(size), 0) AS bytes
            FROM items
            WHERE duplicate_of IS NOT NULL
            """
        ).fetchone()
        return {
            "items": sum(statuses.values()),
            "statuses": dict(statuses),
            "unique_files": int(unique_row["count"]),
            "duplicate_bytes_saved": int(duplicate_row["bytes"]),
            "pending": sum(
                statuses.get(name, 0)
                for name in (
                    "pending",
                    "failed",
                    "source_changed",
                    "removal_failed",
                    "legacy_verification_required",
                )
            ),
            "awaiting_upload": statuses.get("awaiting_upload", 0),
            "ready_to_remove": statuses.get("ready_to_remove", 0),
            "removed": statuses.get("removed", 0),
            "removed_unconfirmed": statuses.get("removed_unconfirmed", 0),
        }


def _legacy_path_for(database_path):
    return Path(database_path).with_suffix(".json")


def _legacy_status(status):
    if status == "removed":
        return "removed"
    if status in {
        "local_verified",
        "awaiting_upload",
        "ready_to_remove",
        "removal_failed",
    }:
        return "legacy_verification_required"
    if status in {"source_missing", "removed_unconfirmed"}:
        return status
    return "pending"


def migrate_legacy_manifest(store, legacy_path):
    """Import the prior JSON once, without deleting or renaming that evidence."""
    legacy_path = Path(legacy_path)
    if not legacy_path.is_file() or store.get_meta("legacy_imported_at"):
        return {"imported": 0, "source": None}
    with open(legacy_path, encoding="utf-8") as stream:
        manifest = json.load(stream)
    if not isinstance(manifest.get("items"), list):
        raise ValueError("旧归档清单缺少 items")  # noqa: TRY004
    if _resolved(manifest.get("archive_root", "")) != store.archive_root:
        raise ValueError("旧归档清单对应另一个目标文件夹")

    imported = 0
    now = utc_now()
    with store.connection:
        for item in manifest["items"]:
            source = item.get("source")
            account_root = item.get("account_root")
            if not source or not account_root:
                continue
            store.connection.execute(
                """
                INSERT OR IGNORE INTO items(
                    source, account_root, account, conversation, year, month,
                    kind, size, mtime_ns, status, sha256, archive_relative,
                    duplicate_of, upload_state, icloud_status_json, error,
                    attempts, created_at, updated_at, removed_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    account_root,
                    item.get("account", "unknown_account"),
                    item.get("conversation", "unknown_conversation"),
                    item.get("year", "unknown_year"),
                    item.get("month", "unknown_month"),
                    item.get("kind", "other"),
                    max(int(item.get("size", 0)), 0),
                    max(int(item.get("mtime_ns", 0)), 0),
                    _legacy_status(item.get("status")),
                    item.get("sha256"),
                    item.get("archive_relative"),
                    item.get("duplicate_of"),
                    item.get("upload_state", "not_checked"),
                    json.dumps(item.get("icloud_status"), ensure_ascii=False)
                    if item.get("icloud_status") is not None
                    else None,
                    "由旧版 JSON 导入；再次归档校验前不会清理源文件",
                    0,
                    manifest.get("created_at", now),
                    now,
                    item.get("removed_at"),
                ),
            )
            imported += store.connection.execute(
                "SELECT changes() AS count"
            ).fetchone()["count"]
        store.set_meta("legacy_imported_at", now)
        store.set_meta("legacy_imported_from", str(legacy_path))
        store.set_meta(
            "legacy_import_sha256",
            sha256_file(legacy_path),
        )
        store.set_meta("legacy_marker_pending", "1")
    return {"imported": int(imported), "source": str(legacy_path)}


@contextmanager
def open_archive_store(
    database_path,
    archive_root,
    batch_bytes=None,
    migrate_legacy=True,
):
    database_path = Path(database_path)
    was_present = database_path.exists()
    store = ArchiveStore(database_path, archive_root, batch_bytes)
    try:
        if migrate_legacy and not was_present:
            migrate_legacy_manifest(store, _legacy_path_for(database_path))
        store.reconcile_interrupted()
        yield store
    finally:
        store.close()


def sanitize_component(value, fallback, max_length=96):
    value = unicodedata.normalize("NFKC", str(value or "")).strip()
    value = "".join(
        "_" if char in {"/", "\\", ":", "\0"} or ord(char) < 32 else char
        for char in value
    )
    value = re.sub(r"\s+", " ", value).strip(" .")
    if value in {"", ".", ".."}:
        value = fallback
    if len(value) > max_length:
        suffix = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
        value = value[: max_length - 10].rstrip() + "__" + suffix
    return value


def classify_file(path, category=None, account_root=None):
    if category == "cache":
        return "cache"
    if category == "video":
        return "video"
    if category == "image":
        return "image"
    path_for_classification = Path(path)
    if account_root is not None:
        try:
            path_for_classification = _resolved(path).relative_to(
                _resolved(account_root)
            )
        except ValueError:
            pass
    lower_parts = {part.lower() for part in path_for_classification.parts}
    if lower_parts & {"cache", "caches", "temp", "tmp", "logs", "apm_record"}:
        return "cache"
    if "video" in lower_parts or "videos" in lower_parts:
        return "video"
    extension = Path(path).suffix.lower()
    if extension in IMAGE_EXTS:
        return "image"
    if extension in VIDEO_EXTS:
        return "video"
    if extension in AUDIO_EXTS:
        return "audio"
    if extension in DOCUMENT_EXTS:
        return "document"
    if extension in ARCHIVE_EXTS:
        return "archive"
    if extension in CACHE_EXTS:
        return "cache"
    if category in {"file", "document", "archive", "other"}:
        return "file"
    return "other"


def infer_month(path, mtime_ns):
    for part in reversed(Path(path).parts):
        match = MONTH_PATTERN.match(part)
        if match:
            return match.group("year"), part
    timestamp = datetime.fromtimestamp(
        mtime_ns / 1_000_000_000,
        tz=timezone.utc,
    ).astimezone()
    return f"{timestamp.year:04d}", f"{timestamp.year:04d}-{timestamp.month:02d}"


def infer_conversation(path, account_root):
    try:
        relative_parts = list(
            _resolved(path).relative_to(_resolved(account_root)).parts
        )
    except ValueError:
        relative_parts = list(Path(path).parts)
    lower = [part.lower() for part in relative_parts]
    marker_sequences = (
        ("filestorage", "msgattach"),
        ("msg", "attach"),
        ("msgattach",),
        ("attach",),
    )
    for sequence in marker_sequences:
        width = len(sequence)
        for index in range(len(lower) - width):
            if tuple(lower[index : index + width]) != sequence:
                continue
            candidate = relative_parts[index + width]
            if MONTH_PATTERN.match(candidate):
                continue
            if candidate.lower() in {"img", "image", "rec", "thumb", "video"}:
                continue
            return sanitize_component(candidate, "unknown_conversation")
    return "unknown_conversation"


def infer_item_metadata(path, account_root, account_id=None, category=None):
    stat_result = os.stat(path, follow_symlinks=False)
    year, month = infer_month(path, stat_result.st_mtime_ns)
    return {
        "account": sanitize_component(
            account_id or Path(account_root).name,
            "unknown_account",
        ),
        "conversation": infer_conversation(path, account_root),
        "year": year,
        "month": month,
        "kind": classify_file(path, category, account_root=account_root),
        "size": stat_result.st_size,
        "mtime_ns": stat_result.st_mtime_ns,
    }


def _iter_source_files(path):
    path = _resolved(path)
    if path.is_symlink():
        return
    if path.is_file():
        yield path
        return
    if not path.is_dir():
        return
    for root, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(root) / name).is_symlink()]
        for name in files:
            candidate = Path(root) / name
            if not candidate.is_symlink() and candidate.is_file():
                yield candidate


def _source_record(source):
    if isinstance(source, (str, os.PathLike)):
        return {"path": str(source)}
    if not isinstance(source, dict) or not source.get("path"):
        raise ValueError("归档源必须包含 path")
    return source


def add_sources(store, sources):
    existing = {
        row["source"]: row
        for row in store.connection.execute(
            "SELECT source, size, mtime_ns, status FROM items"
        ).fetchall()
    }
    added = 0
    refreshed = 0
    skipped = 0
    now = utc_now()
    with store.connection:
        for raw_source in sources:
            source = _source_record(raw_source)
            source_path = _resolved(source["path"])
            account_root = _resolved(source.get("account_root") or source_path.parent)
            if _is_relative_to(store.archive_root, account_root):
                raise ValueError("归档目标不能放在微信数据目录内部")
            if source_path.is_dir() and _is_relative_to(
                store.archive_root,
                source_path,
            ):
                raise ValueError("归档目标不能放在待归档目录内部")
            if _is_relative_to(source_path, store.archive_root):
                raise ValueError("不能把归档目标重新加入归档状态库")

            any_file = False
            for file_path in _iter_source_files(source_path):
                any_file = True
                if file_path.suffix.lower() in PROTECTED_EXTS:
                    store.connection.execute(
                        "INSERT INTO skipped(source, reason, created_at) VALUES(?, ?, ?)",
                        (str(file_path), "protected_extension", now),
                    )
                    skipped += 1
                    continue
                metadata = infer_item_metadata(
                    file_path,
                    account_root,
                    account_id=source.get("account_id"),
                    category=source.get("category"),
                )
                key = str(file_path)
                current = existing.get(key)
                if current is None:
                    store.connection.execute(
                        """
                        INSERT INTO items(
                            source, account_root, account, conversation, year,
                            month, kind, size, mtime_ns, status, upload_state,
                            attempts, created_at, updated_at
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending',
                                 'not_checked', 0, ?, ?)
                        """,
                        (
                            key,
                            str(account_root),
                            metadata["account"],
                            metadata["conversation"],
                            metadata["year"],
                            metadata["month"],
                            metadata["kind"],
                            metadata["size"],
                            metadata["mtime_ns"],
                            now,
                            now,
                        ),
                    )
                    existing[key] = {
                        "size": metadata["size"],
                        "mtime_ns": metadata["mtime_ns"],
                        "status": "pending",
                    }
                    added += 1
                    continue
                fingerprint_changed = (
                    current["size"] != metadata["size"]
                    or current["mtime_ns"] != metadata["mtime_ns"]
                )
                retryable = current["status"] in {
                    "failed",
                    "source_changed",
                    "source_missing",
                    "removal_failed",
                    "removed_unconfirmed",
                    "removed",
                }
                if fingerprint_changed or retryable:
                    store.connection.execute(
                        """
                        UPDATE items
                        SET account_root = ?, account = ?, conversation = ?,
                            year = ?, month = ?, kind = ?, size = ?, mtime_ns = ?,
                            status = 'pending', sha256 = NULL,
                            archive_relative = NULL, duplicate_of = NULL,
                            upload_state = 'not_checked',
                            icloud_status_json = NULL, error = NULL,
                            attempts = 0, removed_at = NULL,
                            removal_started_at = NULL, updated_at = ?
                        WHERE source = ?
                        """,
                        (
                            str(account_root),
                            metadata["account"],
                            metadata["conversation"],
                            metadata["year"],
                            metadata["month"],
                            metadata["kind"],
                            metadata["size"],
                            metadata["mtime_ns"],
                            now,
                            key,
                        ),
                    )
                    existing[key] = {
                        "size": metadata["size"],
                        "mtime_ns": metadata["mtime_ns"],
                        "status": "pending",
                    }
                    refreshed += 1
            if not any_file and not source_path.exists():
                store.connection.execute(
                    "INSERT INTO skipped(source, reason, created_at) VALUES(?, ?, ?)",
                    (str(source_path), "source_missing", now),
                )
                skipped += 1
        store.set_meta("updated_at", now)
    return {"added": added, "refreshed": refreshed, "skipped": skipped}


def sha256_file(path, chunk_bytes=COPY_CHUNK_BYTES):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(chunk_bytes)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _stable_source_digest(source):
    before = source.stat()
    digest = sha256_file(source)
    after = source.stat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if not all(getattr(before, field) == getattr(after, field) for field in fields):
        raise OSError("源文件在哈希校验期间发生变化")
    return digest, after


def _destination_for(item, archive_root, digest):
    filename = sanitize_component(Path(item["source"]).name, "unnamed_file", 180)
    base = (
        archive_root
        / sanitize_component(item["year"], "unknown_year")
        / sanitize_component(item["month"], "unknown_month")
        / sanitize_component(item["account"], "unknown_account")
        / sanitize_component(item["conversation"], "unknown_conversation")
        / KIND_LABELS.get(item["kind"], "other")
    )
    destination = base / filename
    if destination.exists():
        try:
            if destination.is_file() and sha256_file(destination) == digest:
                return destination
        except OSError:
            pass
        stem = sanitize_component(destination.stem, "unnamed_file", 140)
        destination = base / f"{stem}__{digest[:10]}{destination.suffix}"
        if destination.exists():
            if destination.is_file() and sha256_file(destination) == digest:
                return destination
            raise FileExistsError("归档目标的哈希后缀路径已被其他内容占用")
    return destination


def _nearest_existing_parent(path):
    candidate = Path(path)
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _ensure_copy_space(destination, source_size):
    usage = shutil.disk_usage(_nearest_existing_parent(destination))
    required = max(int(source_size), 0) + MIN_FREE_SPACE_RESERVE
    if usage.free < required:
        message = (
            "可用磁盘空间不足：归档前至少需保留 "
            f"{MIN_FREE_SPACE_RESERVE // (1024 * 1024)} MB 安全余量"
        )
        raise OSError(errno.ENOSPC, message, str(destination))


def _ensure_state_write_space(database_path):
    usage = shutil.disk_usage(_nearest_existing_parent(database_path))
    if usage.free < MIN_STATE_FREE_SPACE_RESERVE:
        message = (
            "本地状态库可用空间不足：清理源文件前至少需保留 "
            f"{MIN_STATE_FREE_SPACE_RESERVE // (1024 * 1024)} MB"
        )
        raise OSError(errno.ENOSPC, message, str(database_path))


def _copy_and_verify(source, destination, expected_digest, source_size):
    destination.parent.mkdir(parents=True, exist_ok=True)
    _ensure_copy_space(destination, source_size)
    temporary = destination.with_name(
        f".{destination.name}.cleanmywechat-part-{os.getpid()}"
    )
    try:
        if temporary.exists():
            temporary.unlink()
        with open(source, "rb") as input_stream, open(temporary, "xb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream, COPY_CHUNK_BYTES)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        shutil.copystat(source, temporary, follow_symlinks=False)
        if sha256_file(temporary) != expected_digest:
            raise OSError("归档副本哈希校验失败")
        os.replace(temporary, destination)
        if sha256_file(destination) != expected_digest:
            raise OSError("归档目标哈希校验失败")
    finally:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass


def _marker_path(archive_root):
    return Path(archive_root) / ARCHIVE_MARKER_NAME


def verify_archive_marker(store):
    if not store.archive_root.is_dir():
        raise FileNotFoundError("归档文件夹不存在，已阻止清理源文件")
    marker_path = _marker_path(store.archive_root)
    if not marker_path.is_file():
        raise FileNotFoundError("归档身份标记不存在，已阻止清理源文件")
    try:
        with open(marker_path, encoding="utf-8") as stream:
            marker = json.load(stream)
    except (OSError, ValueError) as exc:
        raise ValueError("归档身份标记无法读取，已阻止清理源文件") from exc
    if marker.get("archive_id") != store.archive_id:
        raise ValueError("归档文件夹与本地状态库不匹配，已阻止清理源文件")
    return marker


def ensure_archive_marker(store):
    marker_path = _marker_path(store.archive_root)
    if marker_path.exists():
        verify_archive_marker(store)
        return marker_path
    if (
        store.count_archived_records()
        and store.get_meta("legacy_marker_pending") != "1"
    ):
        raise FileNotFoundError("既有归档的身份标记已丢失，已停止写入")
    if not store.archive_root.exists() and store.count_archived_records():
        raise FileNotFoundError("既有归档文件夹已丢失，已停止写入")
    store.archive_root.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(
        marker_path,
        {
            "schema_version": SCHEMA_VERSION,
            "archive_id": store.archive_id,
            "created_at": store.get_meta("created_at"),
            "state": "Clean My WeChat archive identity marker",
        },
    )
    with store.connection:
        store.set_meta("legacy_marker_pending", "0")
    return marker_path


def _canonical_by_digest(store, digest, excluding_source):
    return store.connection.execute(
        """
        SELECT * FROM items
        WHERE sha256 = ?
          AND source != ?
          AND duplicate_of IS NULL
          AND archive_relative IS NOT NULL
          AND status IN (
              'local_verified', 'awaiting_upload', 'ready_to_remove',
              'removed', 'removed_unconfirmed'
          )
        ORDER BY rowid
        LIMIT 1
        """,
        (digest, excluding_source),
    ).fetchone()


def _emit_progress(callback, percent, message):
    if callback:
        callback(int(max(0, min(percent, 100))), message)


def _select_byte_limited(rows, byte_limit, item_limit=None):
    selected = []
    selected_bytes = 0
    limit = max(int(byte_limit), 1)
    for row in rows:
        if item_limit is not None and len(selected) >= max(int(item_limit), 1):
            break
        size = max(int(row["size"]), 0)
        if selected and selected_bytes + size > limit:
            break
        selected.append(row)
        selected_bytes += size
        if selected_bytes >= limit:
            break
    return selected, selected_bytes


def process_next_batch(store, progress_callback=None):
    ensure_archive_marker(store)
    candidates = store.connection.execute(
        """
        SELECT * FROM items
        WHERE status IN (
            'pending', 'failed', 'source_changed',
            'legacy_verification_required'
        )
          AND attempts < 3
        ORDER BY rowid
        """
    ).fetchall()
    selected, selected_bytes = _select_byte_limited(
        candidates,
        store.batch_bytes,
        item_limit=DEFAULT_BATCH_ITEMS,
    )
    copied = 0
    duplicates = 0
    failed = 0
    for index, row in enumerate(selected, 1):
        source = Path(row["source"])
        store.update_item(
            row["source"],
            status="archiving",
            attempts=int(row["attempts"]) + 1,
            error=None,
        )
        try:
            if source.is_symlink() or not source.is_file():
                raise FileNotFoundError("源文件不存在或不是普通文件")
            digest, stat_result = _stable_source_digest(source)
            metadata = infer_item_metadata(
                source,
                row["account_root"],
                account_id=row["account"],
                category=row["kind"],
            )
            existing = _canonical_by_digest(store, digest, row["source"])
            if existing is not None:
                destination = store.archive_root / existing["archive_relative"]
                if not destination.is_file() or sha256_file(destination) != digest:
                    raise OSError("重复文件对应的归档副本不可用")
                owner_status = existing["status"]
                if owner_status in {
                    "ready_to_remove",
                    "removed",
                    "removed_unconfirmed",
                }:
                    duplicate_status = "ready_to_remove"
                elif owner_status == "awaiting_upload":
                    duplicate_status = "awaiting_upload"
                else:
                    duplicate_status = "local_verified"
                store.update_item(
                    row["source"],
                    **metadata,
                    sha256=digest,
                    archive_relative=existing["archive_relative"],
                    duplicate_of=existing["source"],
                    status=duplicate_status,
                    upload_state=existing["upload_state"],
                    error=None,
                )
                duplicates += 1
            else:
                item = dict(row)
                item.update(metadata)
                destination = _destination_for(item, store.archive_root, digest)
                if not destination.exists():
                    _copy_and_verify(
                        source,
                        destination,
                        digest,
                        stat_result.st_size,
                    )
                    copied += 1
                elif sha256_file(destination) != digest:
                    raise OSError("归档目标存在同名的不同内容")
                store.update_item(
                    row["source"],
                    **metadata,
                    sha256=digest,
                    archive_relative=str(destination.relative_to(store.archive_root)),
                    duplicate_of=None,
                    status="local_verified",
                    upload_state="not_checked",
                    error=None,
                )
        except Exception as exc:  # noqa: BLE001 - isolate a failed source item
            store.update_item(
                row["source"],
                status="failed",
                error=str(exc),
            )
            failed += 1
        _emit_progress(
            progress_callback,
            index / max(len(selected), 1) * 75,
            f"归档并校验 {index}/{len(selected)}",
        )
    return {
        "selected": len(selected),
        "selected_bytes": selected_bytes,
        "copied": copied,
        "duplicates": duplicates,
        "failed": failed,
    }


def refresh_upload_states(
    store,
    upload_checker=query_icloud_status,
    progress_callback=None,
):
    verify_archive_marker(store)
    canonical = store.connection.execute(
        """
        SELECT * FROM items
        WHERE archive_relative IS NOT NULL
          AND duplicate_of IS NULL
          AND status IN (
              'local_verified', 'awaiting_upload'
          )
        ORDER BY CASE status WHEN 'local_verified' THEN 0 ELSE 1 END, rowid
        LIMIT ?
        """,
        (DEFAULT_UPLOAD_CHECK_ITEMS,),
    ).fetchall()
    destinations = {
        row["source"]: store.archive_root / row["archive_relative"] for row in canonical
    }
    if upload_checker is query_icloud_status:
        default_states = query_icloud_statuses(destinations.values())
    else:
        default_states = {}

    ready = 0
    waiting = 0
    failed = 0
    digest_states = {}
    for index, row in enumerate(canonical, 1):
        destination = destinations[row["source"]]
        try:
            if not destination.is_file():
                raise FileNotFoundError("归档副本不存在")
            if upload_checker is query_icloud_status:
                state = default_states[str(_resolved(destination))]
            else:
                state = upload_checker(destination)
            if state.get("is_icloud") is False:
                status = "ready_to_remove"
                upload_state = "not_icloud"
                ready += 1
            elif (
                state.get("is_icloud") is True
                and state.get("uploaded") is True
                and state.get("uploading") is not True
                and not state.get("upload_error")
                and not state.get("status_error")
            ):
                status = "ready_to_remove"
                upload_state = "uploaded"
                ready += 1
            else:
                status = "awaiting_upload"
                upload_state = (
                    "uploading" if state.get("uploading") else "awaiting_upload"
                )
                waiting += 1
            error = state.get("upload_error") or state.get("status_error")
            store.update_item(
                row["source"],
                status=status,
                upload_state=upload_state,
                icloud_status_json=json.dumps(state, ensure_ascii=False),
                error=error,
            )
            digest_states[row["sha256"]] = (status, upload_state, error)
        except Exception as exc:  # noqa: BLE001 - an unknown cloud state must retain source
            store.update_item(
                row["source"],
                status="awaiting_upload",
                upload_state="status_error",
                error=str(exc),
            )
            digest_states[row["sha256"]] = (
                "awaiting_upload",
                "status_error",
                str(exc),
            )
            failed += 1
        _emit_progress(
            progress_callback,
            75 + index / max(len(canonical), 1) * 25,
            f"检查上传状态 {index}/{len(canonical)}",
        )

    with store.connection:
        for digest, state in digest_states.items():
            owner_status, upload_state, error = state
            duplicate_status = (
                "ready_to_remove"
                if owner_status in {"ready_to_remove", "removed"}
                else "awaiting_upload"
            )
            store.connection.execute(
                """
                UPDATE items
                SET status = ?, upload_state = ?, error = ?, updated_at = ?
                WHERE sha256 = ? AND duplicate_of IS NOT NULL
                """,
                (
                    duplicate_status,
                    upload_state,
                    None if duplicate_status == "ready_to_remove" else error,
                    utc_now(),
                    digest,
                ),
            )
    return {
        "checked": len(canonical),
        "ready": ready,
        "waiting": waiting,
        "failed": failed,
    }


def _verify_archive_copy(row, archive_root):
    destination = archive_root / row["archive_relative"]
    if not destination.is_file():
        raise FileNotFoundError("归档副本不存在")
    if sha256_file(destination) != row["sha256"]:
        raise OSError("归档副本内容已变化")


def get_removal_preview(
    database_path,
    archive_root,
    max_items=DEFAULT_REMOVAL_ITEMS,
    max_bytes=DEFAULT_REMOVAL_BYTES,
):
    with (
        archive_lock(database_path),
        open_archive_store(
            database_path,
            archive_root,
            migrate_legacy=True,
        ) as store,
    ):
        verify_archive_marker(store)
        ready = store.items_with_status(("ready_to_remove",))
        selected, selected_bytes = _select_byte_limited(
            ready,
            max_bytes,
            item_limit=max_items,
        )
        total_bytes = sum(max(int(row["size"]), 0) for row in ready)
        return {
            "eligible_items": len(ready),
            "eligible_bytes": total_bytes,
            "batch_items": len(selected),
            "batch_bytes": selected_bytes,
            "max_items": max(int(max_items), 1),
            "max_bytes": max(int(max_bytes), 1),
            "archive_root": str(store.archive_root),
            "icloud_target": is_probable_icloud_path(store.archive_root),
            "summary": store.summary(),
        }


def remove_ready_sources(
    store,
    confirmed=False,
    max_items=DEFAULT_REMOVAL_ITEMS,
    max_bytes=DEFAULT_REMOVAL_BYTES,
    trash_func=_send2trash,
    progress_callback=None,
):
    if not confirmed:
        raise PermissionError("清理源文件需要单独确认")
    verify_archive_marker(store)
    _ensure_state_write_space(store.path)
    ready = store.items_with_status(("ready_to_remove",))
    selected, selected_bytes = _select_byte_limited(
        ready,
        max_bytes,
        item_limit=max_items,
    )
    removed = 0
    changed = 0
    failed = 0
    unconfirmed = 0
    for index, row in enumerate(selected, 1):
        source = Path(row["source"])
        try:
            if not source.exists():
                store.update_item(
                    row["source"],
                    status="source_missing",
                    error="源文件在清理开始前已不存在，无法确认原因",
                )
                failed += 1
            elif source.is_symlink() or not source.is_file():
                store.update_item(
                    row["source"],
                    status="source_changed",
                    error="源路径不再是原普通文件",
                )
                changed += 1
            else:
                _verify_archive_copy(row, store.archive_root)
                digest, _stat_result = _stable_source_digest(source)
                if digest != row["sha256"]:
                    store.update_item(
                        row["source"],
                        status="source_changed",
                        error="源文件内容已变化，已保留",
                    )
                    changed += 1
                else:
                    _ensure_state_write_space(store.path)
                    store.update_item(
                        row["source"],
                        status="removing",
                        removal_started_at=utc_now(),
                        error=None,
                    )
                    trash_func(str(source))
                    if source.exists():
                        raise OSError("废纸篓操作完成后源路径仍然存在")
                    store.update_item(
                        row["source"],
                        status="removed",
                        removed_at=utc_now(),
                        removal_started_at=None,
                        error=None,
                    )
                    removed += 1
        except Exception as exc:  # noqa: BLE001 - trash adapters can raise platform errors
            current = store.item(row["source"])
            if (
                current is not None
                and current["status"] == "removing"
                and not source.exists()
            ):
                store.update_item(
                    row["source"],
                    status="removed_unconfirmed",
                    removal_started_at=None,
                    error=f"废纸篓操作后状态写入失败或中断：{exc}",
                )
                unconfirmed += 1
            else:
                store.update_item(
                    row["source"],
                    status="removal_failed",
                    removal_started_at=None,
                    error=str(exc),
                )
                failed += 1
        _emit_progress(
            progress_callback,
            index / max(len(selected), 1) * 100,
            f"移入废纸篓 {index}/{len(selected)}",
        )
    return {
        "selected": len(selected),
        "selected_bytes": selected_bytes,
        "removed": removed,
        "changed": changed,
        "failed": failed,
        "unconfirmed": unconfirmed,
    }


def run_archive_cycle(
    database_path,
    archive_root,
    sources,
    batch_bytes=DEFAULT_BATCH_BYTES,
    upload_checker=query_icloud_status,
    progress_callback=None,
):
    """Archive and verify one batch. This function never removes source files."""
    with (
        archive_lock(database_path),
        open_archive_store(
            database_path,
            archive_root,
            batch_bytes=batch_bytes,
            migrate_legacy=True,
        ) as store,
    ):
        add_result = add_sources(store, sources)
        _emit_progress(progress_callback, 1, "本地归档状态已更新")
        batch_result = process_next_batch(
            store,
            progress_callback=progress_callback,
        )
        upload_result = refresh_upload_states(
            store,
            upload_checker=upload_checker,
            progress_callback=progress_callback,
        )
        cycle = {
            "completed_at": utc_now(),
            "add": add_result,
            "batch": batch_result,
            "upload": upload_result,
        }
        with store.connection:
            store.set_meta(
                "last_archive_cycle",
                json.dumps(cycle, ensure_ascii=False),
            )
        summary = store.summary()
        store.checkpoint()
        _emit_progress(progress_callback, 100, "本批归档已完成，源文件保持不变")
        return {
            "operation": "archive",
            "database": str(Path(database_path)),
            "archive_root": str(store.archive_root),
            "add": add_result,
            "batch": batch_result,
            "upload": upload_result,
            "removal": {
                "selected": 0,
                "removed": 0,
                "changed": 0,
                "failed": 0,
                "unconfirmed": 0,
            },
            "summary": summary,
        }


def run_removal_cycle(
    database_path,
    archive_root,
    confirmed=False,
    max_items=DEFAULT_REMOVAL_ITEMS,
    max_bytes=DEFAULT_REMOVAL_BYTES,
    trash_func=_send2trash,
    progress_callback=None,
):
    """Remove one bounded batch only after a separate, explicit confirmation."""
    with (
        archive_lock(database_path),
        open_archive_store(
            database_path,
            archive_root,
            migrate_legacy=True,
        ) as store,
    ):
        removal = remove_ready_sources(
            store,
            confirmed=confirmed,
            max_items=max_items,
            max_bytes=max_bytes,
            trash_func=trash_func,
            progress_callback=progress_callback,
        )
        cycle = {
            "completed_at": utc_now(),
            "removal": removal,
        }
        with store.connection:
            store.set_meta(
                "last_removal_cycle",
                json.dumps(cycle, ensure_ascii=False),
            )
        summary = store.summary()
        store.checkpoint()
        _emit_progress(progress_callback, 100, "本批源文件已处理")
        return {
            "operation": "remove",
            "database": str(Path(database_path)),
            "archive_root": str(store.archive_root),
            "removal": removal,
            "summary": summary,
        }
