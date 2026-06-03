import json
import os
import shutil
from datetime import datetime
from pathlib import Path


PROTECTED_EXTS = {
    ".db", ".sqlite", ".sqlite3", ".db-shm", ".db-wal", ".ldb", ".sst",
    ".dll", ".exe", ".msi", ".sys", ".ocx", ".pyd", ".so", ".dylib",
    ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jar", ".pak",
}


def is_protected_file(file_path):
    return os.path.splitext(str(file_path))[1].lower() in PROTECTED_EXTS


def human_size(num_bytes):
    value = float(num_bytes or 0)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


def path_size(path):
    path = Path(path)
    try:
        if path.is_file() or path.is_symlink():
            return path.stat().st_size
        if path.is_dir():
            total = 0
            for root, dirs, files in os.walk(path):
                root_path = Path(root)
                dirs[:] = [name for name in dirs if not (root_path / name).is_symlink()]
                for filename in files:
                    try:
                        total += (root_path / filename).stat().st_size
                    except OSError:
                        continue
            return total
    except OSError:
        return 0
    return 0


def permanent_delete(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def delete_path_for_manifest(file_path, item_type, direct_delete=False, trash_func=None, delete_func=None):
    size_bytes = path_size(file_path)
    record = {
        "path": str(file_path),
        "type": item_type,
        "action": "delete" if direct_delete else "trash",
        "status": "",
        "size_bytes": size_bytes,
        "size": human_size(size_bytes),
        "error": "",
    }
    if not os.path.exists(file_path):
        record["status"] = "skipped"
        record["reason"] = "missing"
        return record
    if is_protected_file(file_path):
        record["status"] = "skipped"
        record["reason"] = "protected_extension"
        return record
    try:
        if direct_delete:
            (delete_func or permanent_delete)(file_path)
            record["status"] = "deleted"
        else:
            if trash_func is None:
                raise RuntimeError("trash_func is not configured")
            trash_func(file_path)
            record["status"] = "trashed"
    except Exception as exc:  # noqa: BLE001 - persisted for the cleanup report.
        record["status"] = "failed"
        record["error"] = str(exc)
    return record


def cleanup_result_summary(records, direct_delete=False):
    processed = [row for row in records if row.get("status") in {"deleted", "trashed"}]
    skipped = [row for row in records if row.get("status") == "skipped"]
    failed = [row for row in records if row.get("status") == "failed"]
    processed_size = sum(row.get("size_bytes", 0) for row in processed)
    return {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "action": "delete" if direct_delete else "trash",
        "direct_delete": direct_delete,
        "total_count": len(records),
        "processed_count": len(processed),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "processed_size_bytes": processed_size,
        "processed_size": human_size(processed_size),
        "records": records,
    }


def combine_cleanup_results(results):
    records = []
    direct_delete = False
    for result in results:
        records.extend(result.get("records", []))
        direct_delete = direct_delete or bool(result.get("direct_delete"))
    return cleanup_result_summary(records, direct_delete=direct_delete)


def write_cleanup_manifest(result, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = output_dir / f"cleanup_manifest_{stamp}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
