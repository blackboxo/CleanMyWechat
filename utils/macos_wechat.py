import csv
import hashlib
import html
import json
import os
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

try:
    from send2trash import send2trash
except ImportError:  # pragma: no cover - dependency is declared for normal app use.
    send2trash = None


MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
DEFAULT_CUTOFF_MONTH = "2025-06"
DEFAULT_DUPLICATE_THRESHOLD = 50 * 1024 * 1024
DEFAULT_LARGE_FILE_THRESHOLD = 100 * 1024 * 1024

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".m4v", ".3gp"}
DOCUMENT_EXTS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".txt", ".csv"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"}
DATA_EXTS = {".dta", ".sav", ".json", ".sqlite", ".db"}
DESIGN_EXTS = {".psd", ".ai", ".sketch"}
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".flac"}

KIND_ORDER = [
    "Archives",
    "PDF",
    "PowerPoint",
    "Word",
    "Excel",
    "Images",
    "Video",
    "Audio",
    "Data",
    "Design",
    "Text",
    "Other",
]

CLEANUP_CATEGORY_LABELS = {
    "msg_file": "接收文件",
    "msg_video": "视频",
    "msg_attach": "图片/附件",
    "account_cache": "账号缓存",
    "wxwork_data": "企业微信数据",
    "image": "图片",
    "video": "视频",
    "file": "文件",
    "cache": "缓存",
}

DEFAULT_CLEANUP_OPTIONS = {
    "min_age_days": 365,
    "use_whitelist": True,
    "whitelist_paths": [],
    "whitelist_exts": [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf"],
    "categories": {
        "image": True,
        "video": True,
        "file": False,
        "cache": True,
    },
}


def emit_progress(callback, percent, message, phase="scan"):
    if not callback:
        return
    event = {
        "percent": max(0, min(100, int(percent))),
        "message": message,
        "phase": phase,
    }
    try:
        callback(event)
    except TypeError:
        callback(event["percent"], event["message"])


@dataclass
class FileRecord:
    name: str
    path: str
    account: str
    source: str
    month: str
    kind: str
    extension: str
    size_bytes: int
    size: str
    mtime: str


@dataclass
class CandidateBucket:
    category: str
    account: str
    month: str
    size_bytes: int
    size: str
    path: str
    note: str


def human_size(num_bytes):
    value = float(num_bytes or 0)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


def default_xwechat_root(home=None):
    home_path = Path(home).expanduser() if home else Path.home()
    return home_path / "Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files"


def common_xwechat_roots(home=None):
    home_path = Path(home).expanduser() if home else Path.home()
    return [
        home_path / "Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files",
        home_path / "Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat",
        home_path / "Documents/xwechat_files",
        home_path / "Library/Containers/com.tencent.WeWorkMac/Data/Documents/WXWork/Users",
        home_path / "Library/Containers/com.tencent.WeWorkMac/Data/Documents/WeWork/Users",
        home_path / "Library/Containers/com.tencent.WeWorkMac/Data/Library/Application Support/WXWork/Data",
    ]


def discover_xwechat_roots(home=None):
    return [path for path in common_xwechat_roots(home) if path.exists()]


def resolve_scan_roots(xwechat_root=None):
    if xwechat_root is None or str(xwechat_root).strip().upper() == "AUTO":
        roots = discover_xwechat_roots()
        return roots or [default_xwechat_root()]
    return [Path(xwechat_root).expanduser()]


def is_account_dir(path):
    if not path or not Path(path).is_dir():
        return False
    name = Path(path).name
    if name in {"all_users", "Backup", "old_backup"}:
        return False
    try:
        names = {child.name for child in Path(path).iterdir()}
    except OSError:
        return False
    if name.startswith("wxid_") and bool({"msg", "cache", "db_storage"} & names):
        return True
    lowered_parts = {part.lower() for part in Path(path).parts}
    if {"wxwork", "wework"} & lowered_parts and ("Data" in names or "data" in names):
        return True
    return False


def account_client_type(account):
    parts = {part.lower() for part in Path(account).parts}
    if {"wxwork", "wework"} & parts:
        return "wxwork"
    return "wechat"


def discover_accounts(xwechat_root):
    root = Path(xwechat_root).expanduser()
    if not root.exists():
        return []
    return sorted([path for path in root.iterdir() if is_account_dir(path)], key=lambda path: path.name)


def discover_accounts_from_roots(roots):
    accounts = []
    seen = set()
    for root in roots:
        for account in discover_accounts(root):
            key = str(account.resolve())
            if key not in seen:
                seen.add(key)
                accounts.append(account)
    return sorted(accounts, key=lambda path: (path.name, str(path)))


def block_size(path):
    try:
        st = Path(path).lstat()
    except OSError:
        return 0
    blocks = getattr(st, "st_blocks", 0)
    if blocks:
        return int(blocks) * 512
    return int(st.st_size)


def tree_size(path):
    path = Path(path)
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        return block_size(path)
    total = block_size(path)
    for root, dirs, files in os.walk(path):
        root_path = Path(root)
        dirs[:] = [name for name in dirs if not (root_path / name).is_symlink()]
        for dirname in dirs:
            total += block_size(root_path / dirname)
        for filename in files:
            total += block_size(root_path / filename)
    return total


def iter_files(root):
    root = Path(root)
    if not root.exists():
        return
    if root.is_file() and not root.is_symlink():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirpath = Path(dirpath)
        dirnames[:] = [name for name in dirnames if not (dirpath / name).is_symlink()]
        for filename in filenames:
            path = dirpath / filename
            if path.is_file() and not path.is_symlink():
                yield path


def file_size(path):
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


def file_mtime(path):
    try:
        return datetime.fromtimestamp(Path(path).stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return ""


def month_from_path(path):
    for part in Path(path).parts:
        if MONTH_RE.match(part):
            return part
    mtime = file_mtime(path)
    return mtime[:7] if mtime else "unknown"


def kind_for_path(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return "PDF"
    if suffix in {".ppt", ".pptx", ".key"}:
        return "PowerPoint"
    if suffix in {".doc", ".docx"}:
        return "Word"
    if suffix in {".xls", ".xlsx"}:
        return "Excel"
    if suffix in ARCHIVE_EXTS:
        return "Archives"
    if suffix in IMAGE_EXTS:
        return "Images"
    if suffix in VIDEO_EXTS:
        return "Video"
    if suffix in AUDIO_EXTS:
        return "Audio"
    if suffix in DATA_EXTS:
        return "Data"
    if suffix in DESIGN_EXTS:
        return "Design"
    if suffix in {".txt", ".md"}:
        return "Text"
    return "Other"


def category_label(category):
    return CLEANUP_CATEGORY_LABELS.get(category, category)


def cleanup_category_for_record(record):
    source = str(record.get("source", "")).lower()
    kind = str(record.get("kind", ""))
    if "cache" in source:
        return "cache"
    if kind == "Images":
        return "image"
    if kind == "Video":
        return "video"
    return "file"


def record_age_days(record, now=None):
    now = now or datetime.now()
    mtime = record.get("mtime") or ""
    try:
        timestamp = datetime.fromisoformat(mtime)
    except ValueError:
        return 0
    return max(0, (now - timestamp).days)


def month_dir_sizes(root):
    result = {}
    root = Path(root)
    if not root.exists():
        return result
    for child in root.iterdir():
        if child.is_dir() and MONTH_RE.match(child.name):
            result[child.name] = tree_size(child)
    return dict(sorted(result.items()))


def attach_month_summary(root):
    result = defaultdict(int)
    root = Path(root)
    if not root.exists():
        return {}
    for path in iter_files(root):
        month = month_from_path(path)
        if MONTH_RE.match(month):
            result[month] += block_size(path)
    return dict(sorted(result.items()))


def merge_month_summaries(*summaries):
    result = defaultdict(int)
    for summary in summaries:
        for month, size in summary.items():
            result[month] += size
    return dict(sorted(result.items()))


def cache_roots_for_account(account):
    candidates = [
        account / "cache",
        account / "temp",
        account / "apm_record",
        account / "business/InputTemp",
        account / "business/emoticon/Temp",
        account / "business/emoticon/Thumb",
        account / "business/xweb",
        account / "Applet",
        account / "WMPF",
        account / "WeChatAppEx",
        account / "XPlugin",
    ]
    return [path for path in candidates if path.exists()]


def _path_under_any(path, roots):
    return any(_path_within(path, root) for root in roots)


def collect_file_records(account, source_name, root, progress_callback=None, progress_base=0, progress_span=0):
    records = []
    indexed = 0
    for path in iter_files(root):
        indexed += 1
        size = file_size(path)
        records.append(
            FileRecord(
                name=path.name,
                path=str(path),
                account=account.name,
                source=source_name,
                month=month_from_path(path),
                kind=kind_for_path(path),
                extension=path.suffix.lower() or "(none)",
                size_bytes=size,
                size=human_size(size),
                mtime=file_mtime(path),
            )
        )
        if indexed % 250 == 0:
            step = min(progress_span - 1, indexed // 250) if progress_span else 0
            emit_progress(
                progress_callback,
                progress_base + step,
                f"正在索引 {account.name} / {source_name}：已记录 {indexed} 个文件",
                "scan",
            )
    return records


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duplicate_groups(
    roots,
    threshold=DEFAULT_DUPLICATE_THRESHOLD,
    progress_callback=None,
    progress_start=72,
    progress_end=94,
):
    by_size = defaultdict(list)
    inspected = 0
    for root in roots:
        for path in iter_files(root):
            inspected += 1
            size = file_size(path)
            if size >= threshold:
                by_size[size].append(path)
            if inspected % 500 == 0:
                emit_progress(
                    progress_callback,
                    min(progress_start + 6, progress_start + inspected // 500),
                    f"正在检查重复候选：已查看 {inspected} 个文件",
                    "duplicates",
                )

    groups = []
    hash_targets = sum(len(paths) for paths in by_size.values() if len(paths) > 1)
    hashed = 0
    if hash_targets:
        emit_progress(progress_callback, progress_start + 8, f"开始哈希 {hash_targets} 个大文件候选", "duplicates")
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash = defaultdict(list)
        for path in paths:
            try:
                by_hash[sha256(path)].append(path)
            except OSError:
                continue
            hashed += 1
            if hashed % 5 == 0 or hashed == hash_targets:
                span = max(1, progress_end - progress_start - 10)
                percent = progress_start + 10 + int(span * hashed / max(1, hash_targets))
                emit_progress(
                    progress_callback,
                    min(progress_end, percent),
                    f"正在比对重复文件：{hashed}/{hash_targets}",
                    "duplicates",
                )
        for digest, matched_paths in by_hash.items():
            if len(matched_paths) < 2:
                continue
            savings = size * (len(matched_paths) - 1)
            groups.append(
                {
                    "sha256": digest,
                    "short_sha": digest[:12],
                    "count": len(matched_paths),
                    "size_bytes": size,
                    "size": human_size(size),
                    "potential_savings_bytes": savings,
                    "potential_savings": human_size(savings),
                    "files": [
                        {
                            "path": str(path),
                            "name": path.name,
                            "month": month_from_path(path),
                            "size": human_size(size),
                        }
                        for path in sorted(matched_paths, key=str)
                    ],
                }
            )
    emit_progress(progress_callback, progress_end, f"重复文件检查完成：发现 {len(groups)} 组", "duplicates")
    return sorted(groups, key=lambda row: row["potential_savings_bytes"], reverse=True)


def summarize_records(records):
    buckets = {
        "by_kind": defaultdict(lambda: {"count": 0, "size_bytes": 0}),
        "by_month": defaultdict(lambda: {"count": 0, "size_bytes": 0}),
        "by_extension": defaultdict(lambda: {"count": 0, "size_bytes": 0}),
        "by_account": defaultdict(lambda: {"count": 0, "size_bytes": 0}),
    }
    total_size = 0
    large_count = 0
    for record in records:
        total_size += record.size_bytes
        if record.size_bytes >= DEFAULT_LARGE_FILE_THRESHOLD:
            large_count += 1
        values = {
            "by_kind": record.kind,
            "by_month": record.month,
            "by_extension": record.extension,
            "by_account": record.account,
        }
        for bucket_name, key in values.items():
            buckets[bucket_name][key]["count"] += 1
            buckets[bucket_name][key]["size_bytes"] += record.size_bytes

    def rows(bucket):
        return [
            {"name": key, "count": value["count"], "size_bytes": value["size_bytes"], "size": human_size(value["size_bytes"])}
            for key, value in sorted(bucket.items(), key=lambda item: item[1]["size_bytes"], reverse=True)
        ]

    return {
        "file_count": len(records),
        "total_size_bytes": total_size,
        "total_size": human_size(total_size),
        "large_file_count": large_count,
        "by_kind": rows(buckets["by_kind"]),
        "by_month": rows(buckets["by_month"]),
        "by_extension": rows(buckets["by_extension"]),
        "by_account": rows(buckets["by_account"]),
    }


def scan_macos_wechat(
    xwechat_root=None,
    cutoff_month=DEFAULT_CUTOFF_MONTH,
    duplicate_threshold=DEFAULT_DUPLICATE_THRESHOLD,
    progress_callback=None,
):
    roots = resolve_scan_roots(xwechat_root)
    emit_progress(progress_callback, 1, "准备扫描 macOS 微信数据目录", "prepare")
    emit_progress(progress_callback, 3, "正在定位微信账号目录", "prepare")
    accounts = discover_accounts_from_roots(roots)
    account_rows = []
    candidates = []
    records = []
    duplicate_roots = []

    total_accounts = max(1, len(accounts))
    for account_index, account in enumerate(accounts, 1):
        client_type = account_client_type(account)
        account_start = 5 + int((account_index - 1) * 58 / total_accounts)
        account_end = 5 + int(account_index * 58 / total_accounts)
        emit_progress(progress_callback, account_start, f"正在扫描账号 {account_index}/{len(accounts)}：{account.name}", "scan")
        sections = {}
        for child in account.iterdir():
            if child.is_dir():
                sections[child.name] = tree_size(child)

        if client_type == "wxwork":
            data_root = account / "Data"
            if not data_root.exists():
                data_root = account / "data"
            duplicate_roots.append(data_root)
            records.extend(
                collect_file_records(
                    account,
                    "wxwork/data",
                    data_root,
                    progress_callback=progress_callback,
                    progress_base=account_start + 2,
                    progress_span=max(1, account_end - account_start - 2),
                )
            )
            months = {"wxwork_data": attach_month_summary(data_root)}
        else:
            msg_file = account / "msg/file"
            msg_video = account / "msg/video"
            msg_attach = account / "msg/attach"
            cache_roots = cache_roots_for_account(account)
            duplicate_roots.extend([msg_file, msg_video, msg_attach])
            duplicate_roots.extend(cache_roots)

            span = max(5, account_end - account_start)
            file_mark = account_start + max(1, span // 4)
            video_mark = account_start + max(2, span // 2)
            attach_mark = account_start + max(3, span * 3 // 4)
            records.extend(
                collect_file_records(
                    account,
                    "msg/file",
                    msg_file,
                    progress_callback=progress_callback,
                    progress_base=account_start + 2,
                    progress_span=max(1, file_mark - account_start - 2),
                )
            )
            records.extend(
                collect_file_records(
                    account,
                    "msg/video",
                    msg_video,
                    progress_callback=progress_callback,
                    progress_base=file_mark,
                    progress_span=max(1, video_mark - file_mark),
                )
            )
            records.extend(
                collect_file_records(
                    account,
                    "msg/attach",
                    msg_attach,
                    progress_callback=progress_callback,
                    progress_base=video_mark,
                    progress_span=max(1, attach_mark - video_mark),
                )
            )
            cache_span = max(1, account_end - attach_mark)
            for cache_index, cache_root in enumerate(cache_roots, 1):
                cache_progress = attach_mark + int(cache_span * (cache_index - 1) / max(1, len(cache_roots)))
                records.extend(
                    collect_file_records(
                        account,
                        f"cache/{cache_root.name}",
                        cache_root,
                        progress_callback=progress_callback,
                        progress_base=cache_progress,
                        progress_span=1,
                    )
                )

            months = {
                "msg_file": month_dir_sizes(msg_file),
                "msg_video": month_dir_sizes(msg_video),
                "msg_attach": attach_month_summary(msg_attach),
                "account_cache": merge_month_summaries(*(attach_month_summary(path) for path in cache_roots)),
            }

        for category, month_sizes in months.items():
            for month, size in month_sizes.items():
                if month < cutoff_month:
                    if client_type == "wxwork":
                        base_path = data_root
                    else:
                        base_path = {
                            "msg_file": msg_file / month,
                            "msg_video": msg_video / month,
                            "msg_attach": msg_attach,
                            "account_cache": account,
                        }[category]
                    note = {
                        "msg_file": "用户可见的接收文件",
                        "msg_video": "用户可见的视频",
                        "msg_attach": "按联系人哈希分组的图片、音频和附件碎片",
                        "account_cache": "账号月份缓存",
                        "wxwork_data": "企业微信账号数据，按文件修改时间识别旧内容",
                    }[category]
                    candidates.append(
                        CandidateBucket(
                            category=category,
                            account=account.name,
                            month=month,
                            size_bytes=size,
                            size=human_size(size),
                            path=str(base_path),
                            note=note,
                        )
                    )

        account_rows.append(
            {
                "name": account.name,
                "client_type": client_type,
                "path": str(account),
                "size_bytes": tree_size(account),
                "size": human_size(tree_size(account)),
                "sections": {
                    key: {"size_bytes": value, "size": human_size(value)}
                    for key, value in sorted(sections.items(), key=lambda item: item[1], reverse=True)
                },
                "months": {
                    key: [
                        {"month": month, "size_bytes": size, "size": human_size(size)}
                        for month, size in sorted(value.items(), key=lambda item: item[1], reverse=True)
                    ]
                    for key, value in months.items()
                },
            }
        )
        emit_progress(progress_callback, account_end, f"账号扫描完成：{account.name}", "scan")

    emit_progress(progress_callback, 66, "正在汇总文件类型、月份和账号统计", "summary")
    top_files = sorted([asdict(record) for record in records], key=lambda row: row["size_bytes"], reverse=True)[:200]
    duplicate_data = duplicate_groups(
        duplicate_roots,
        threshold=duplicate_threshold,
        progress_callback=progress_callback,
        progress_start=72,
        progress_end=94,
    )
    duplicate_savings = sum(group["potential_savings_bytes"] for group in duplicate_data)
    summary = summarize_records(records)
    summary["duplicate_group_count"] = len(duplicate_data)
    summary["duplicate_potential_savings_bytes"] = duplicate_savings
    summary["duplicate_potential_savings"] = human_size(duplicate_savings)

    emit_progress(progress_callback, 96, "正在计算 xwechat_files 总体占用", "summary")
    root_size = sum(tree_size(root) for root in roots)
    emit_progress(progress_callback, 100, "扫描完成", "done")
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "platform": "macOS",
        "xwechat_root": str(roots[0]) if len(roots) == 1 else "AUTO",
        "source_roots": [str(root) for root in roots],
        "xwechat_root_exists": any(root.exists() for root in roots),
        "xwechat_root_size_bytes": root_size,
        "xwechat_root_size": human_size(root_size),
        "cutoff_month": cutoff_month,
        "accounts": account_rows,
        "files": [asdict(record) for record in records],
        "top_files": top_files,
        "summary": summary,
        "duplicates": duplicate_data,
        "candidates": [asdict(candidate) for candidate in sorted(candidates, key=lambda item: item.size_bytes, reverse=True)],
    }


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_scan_outputs(scan_result, output_dir):
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    json_path = output_dir / f"macos_wechat_scan_{stamp}.json"
    files_csv = output_dir / f"macos_wechat_files_{stamp}.csv"
    candidates_csv = output_dir / f"macos_wechat_candidates_{stamp}.csv"
    duplicates_csv = output_dir / f"macos_wechat_duplicates_{stamp}.csv"

    json_path.write_text(json.dumps(scan_result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(files_csv, scan_result["files"])
    write_csv(candidates_csv, scan_result["candidates"])

    duplicate_rows = []
    for group in scan_result["duplicates"]:
        for file_info in group["files"]:
            duplicate_rows.append(
                {
                    "sha256": group["sha256"],
                    "group_count": group["count"],
                    "potential_savings_bytes": group["potential_savings_bytes"],
                    "potential_savings": group["potential_savings"],
                    "size_bytes": group["size_bytes"],
                    "size": group["size"],
                    "path": file_info["path"],
                }
            )
    write_csv(duplicates_csv, duplicate_rows)

    return {
        "json": str(json_path),
        "files_csv": str(files_csv),
        "candidates_csv": str(candidates_csv),
        "duplicates_csv": str(duplicates_csv),
    }


def load_scan_result(path):
    path = Path(path).expanduser()
    return json.loads(path.read_text(encoding="utf-8"))


def scan_history_path(output_dir):
    return Path(output_dir).expanduser() / "reports/scan_history.json"


def load_scan_history(output_dir):
    path = scan_history_path(output_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def record_scan_history(output_dir, scan_result, outputs, dashboard_path=None, summary_path=None, view_path=None, diff=None):
    path = scan_history_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    history = load_scan_history(output_dir)
    entry = {
        "generated_at": scan_result.get("generated_at", datetime.now().isoformat(timespec="seconds")),
        "xwechat_root": scan_result.get("xwechat_root", ""),
        "cutoff_month": scan_result.get("cutoff_month", ""),
        "file_count": scan_result.get("summary", {}).get("file_count", 0),
        "total_size": scan_result.get("summary", {}).get("total_size", "0 B"),
        "total_size_bytes": scan_result.get("summary", {}).get("total_size_bytes", 0),
        "duplicate_group_count": scan_result.get("summary", {}).get("duplicate_group_count", 0),
        "json": outputs.get("json", ""),
        "dashboard": str(dashboard_path or ""),
        "summary": str(summary_path or ""),
        "view": str(view_path or ""),
        "diff": diff or {},
    }
    history = [row for row in history if row.get("json") != entry["json"]]
    history.insert(0, entry)
    path.write_text(json.dumps(history[:50], ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def _signature(record):
    return (record.get("size_bytes", 0), record.get("mtime", ""))


def compare_scan_results(previous_scan, current_scan):
    previous = {row["path"]: row for row in previous_scan.get("files", [])}
    current = {row["path"]: row for row in current_scan.get("files", [])}

    added = [current[path] for path in current.keys() - previous.keys()]
    removed = [previous[path] for path in previous.keys() - current.keys()]
    changed = [current[path] for path in current.keys() & previous.keys() if _signature(current[path]) != _signature(previous[path])]

    return {
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "added_size_bytes": sum(row.get("size_bytes", 0) for row in added),
        "removed_size_bytes": sum(row.get("size_bytes", 0) for row in removed),
        "changed_size_bytes": sum(row.get("size_bytes", 0) for row in changed),
        "added_size": human_size(sum(row.get("size_bytes", 0) for row in added)),
        "removed_size": human_size(sum(row.get("size_bytes", 0) for row in removed)),
        "changed_size": human_size(sum(row.get("size_bytes", 0) for row in changed)),
        "added": added[:200],
        "removed": removed[:200],
        "changed": changed[:200],
    }


def _path_within(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (OSError, ValueError):
        return False


def _source_roots(scan_result):
    roots = scan_result.get("source_roots") or [scan_result.get("xwechat_root", "")]
    return [root for root in roots if root and root != "AUTO"]


def _path_within_sources(path, scan_result):
    return any(_path_within(path, root) for root in _source_roots(scan_result))


def _cleanup_options(options):
    merged = {
        "min_age_days": DEFAULT_CLEANUP_OPTIONS["min_age_days"],
        "use_whitelist": DEFAULT_CLEANUP_OPTIONS["use_whitelist"],
        "whitelist_paths": list(DEFAULT_CLEANUP_OPTIONS["whitelist_paths"]),
        "whitelist_exts": list(DEFAULT_CLEANUP_OPTIONS["whitelist_exts"]),
        "categories": dict(DEFAULT_CLEANUP_OPTIONS["categories"]),
    }
    if options:
        if "min_age_days" in options:
            merged["min_age_days"] = int(options.get("min_age_days", merged["min_age_days"]))
        if "use_whitelist" in options:
            merged["use_whitelist"] = bool(options.get("use_whitelist"))
        if "whitelist_paths" in options:
            merged["whitelist_paths"] = list(options.get("whitelist_paths") or [])
        if "whitelist_exts" in options:
            merged["whitelist_exts"] = list(options.get("whitelist_exts") or [])
        merged["categories"].update(options.get("categories", {}))
    merged["whitelist_exts"] = [
        ext if ext.startswith(".") else f".{ext}"
        for ext in [str(value).strip().lower() for value in merged["whitelist_exts"]]
        if ext
    ]
    merged["whitelist_paths"] = [str(Path(path).expanduser()) for path in merged["whitelist_paths"] if str(path).strip()]
    return merged


def _is_whitelisted(path, options):
    if not options.get("use_whitelist", True):
        return False
    path = Path(path).expanduser()
    if path.suffix.lower() in set(options.get("whitelist_exts", [])):
        return True
    return any(_path_within(path, root) for root in options.get("whitelist_paths", []))


def _candidate_allows_path(candidate, path):
    category = candidate.get("category")
    month = candidate.get("month")
    if category in {"msg_attach", "wxwork_data", "account_cache"} and month_from_path(path) != month:
        return False
    if category == "account_cache":
        return _path_under_any(path, cache_roots_for_account(Path(candidate.get("path", "")).expanduser()))
    return True


def build_cleanup_plan(scan_result, candidate_rows=None, options=None, now=None):
    items = []
    seen = set()
    now = now or datetime.now()
    merged_options = _cleanup_options(options)

    if options is not None:
        min_age_days = max(0, int(merged_options["min_age_days"]))
        enabled = merged_options["categories"]
        for record in scan_result.get("files", []):
            path = Path(record.get("path", "")).expanduser()
            if not path.exists() or not _path_within_sources(path, scan_result):
                continue
            if _is_whitelisted(path, merged_options):
                continue
            category = cleanup_category_for_record(record)
            if not enabled.get(category, False):
                continue
            age_days = record_age_days(record, now=now)
            if age_days < min_age_days:
                continue
            path_key = str(path)
            if path_key in seen:
                continue
            seen.add(path_key)
            items.append(
                {
                    "path": path_key,
                    "name": record.get("name", path.name),
                    "category": category,
                    "category_label": category_label(category),
                    "account": record.get("account", ""),
                    "month": record.get("month", ""),
                    "age_days": age_days,
                    "size_bytes": record.get("size_bytes", 0),
                    "size": record.get("size", human_size(record.get("size_bytes", 0))),
                    "mtime": record.get("mtime", ""),
                }
            )
        items.sort(key=lambda row: row["size_bytes"], reverse=True)
        total_size = sum(row["size_bytes"] for row in items)
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": scan_result.get("xwechat_root", ""),
            "source_roots": _source_roots(scan_result),
            "mode": "type_age",
            "options": merged_options,
            "count": len(items),
            "total_size_bytes": total_size,
            "total_size": human_size(total_size),
            "items": items,
        }

    candidates = candidate_rows if candidate_rows is not None else scan_result.get("candidates", [])
    for candidate in candidates:
        candidate_path = Path(candidate.get("path", "")).expanduser()
        if not candidate_path.exists() or not _path_within_sources(candidate_path, scan_result):
            continue
        for path in iter_files(candidate_path):
            if not _path_within_sources(path, scan_result):
                continue
            if not _candidate_allows_path(candidate, path):
                continue
            if _is_whitelisted(path, merged_options):
                continue
            path_key = str(path)
            if path_key in seen:
                continue
            seen.add(path_key)
            size = file_size(path)
            items.append(
                {
                    "path": path_key,
                    "name": path.name,
                    "category": candidate.get("category", ""),
                    "category_label": category_label(candidate.get("category", "")),
                    "account": candidate.get("account", ""),
                    "month": month_from_path(path),
                    "age_days": record_age_days({"mtime": file_mtime(path)}, now=now),
                    "size_bytes": size,
                    "size": human_size(size),
                    "mtime": file_mtime(path),
                }
            )

    items.sort(key=lambda row: row["size_bytes"], reverse=True)
    total_size = sum(row["size_bytes"] for row in items)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": scan_result.get("xwechat_root", ""),
        "source_roots": _source_roots(scan_result),
        "count": len(items),
        "total_size_bytes": total_size,
        "total_size": human_size(total_size),
        "items": items,
    }


def trash_cleanup_plan(plan, selected_paths=None, progress_callback=None, trash_func=None):
    if trash_func is None:
        if send2trash is None:
            raise RuntimeError("send2trash is not available")
        trash_func = send2trash
    selected = set(selected_paths or [item["path"] for item in plan.get("items", [])])
    items = [item for item in plan.get("items", []) if item.get("path") in selected]
    moved = []
    failed = []
    total = max(1, len(items))

    for index, item in enumerate(items, 1):
        path = item.get("path", "")
        emit_progress(progress_callback, int(index * 100 / total), f"正在移动到回收站：{Path(path).name}", "cleanup")
        try:
            if Path(path).exists():
                trash_func(path)
                moved.append(item)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI/report.
            failed.append({"path": path, "error": str(exc)})

    moved_size = sum(item.get("size_bytes", 0) for item in moved)
    return {
        "moved_count": len(moved),
        "failed_count": len(failed),
        "moved_size_bytes": moved_size,
        "moved_size": human_size(moved_size),
        "failed": failed,
    }


def safe_link_name(path):
    name = Path(path).name.replace("/", "_").replace(":", "_").strip() or "unnamed"
    if len(name) <= 140:
        return name
    suffix = Path(name).suffix
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    stem = Path(name).stem[: 132 - len(suffix)]
    return f"{stem}_{digest}{suffix}"


def create_symlink_view(scan_result, output_dir):
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    created = []

    for record in scan_result["files"]:
        source = Path(record["path"])
        if not source.exists():
            continue
        destinations = [
            output_dir / "by_month" / record["account"] / record["month"],
            output_dir / "by_kind" / record["kind"] / record["month"],
        ]
        if record["size_bytes"] >= DEFAULT_LARGE_FILE_THRESHOLD:
            destinations.append(output_dir / "large_files_over_100MB" / record["month"])
        for dest_dir in destinations:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / safe_link_name(source)
            counter = 1
            while dest.exists() or dest.is_symlink():
                if dest.is_symlink() and os.readlink(dest) == str(source):
                    break
                dest = dest_dir / f"{Path(safe_link_name(source)).stem} [{counter}]{source.suffix}"
                counter += 1
            if not dest.exists() and not dest.is_symlink():
                try:
                    os.symlink(source, dest)
                    created.append(str(dest))
                except OSError:
                    continue

    readme = output_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Clean My WeChat macOS 整理视图",
                "",
                "此文件夹只包含指向微信原文件的符号链接。",
                "删除这里的符号链接不会删除微信原文件。",
                "",
                f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
                f"来源：{scan_result['xwechat_root']}",
            ]
        ),
        encoding="utf-8",
    )
    return {"root": str(output_dir), "created_links": len(created), "readme": str(readme)}


def _json_for_script(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def render_dashboard_html(scan_result):
    data = _json_for_script(scan_result)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>微信文件检查 Dashboard</title>
  <style>
    :root {{
      --bg:#edf3f6; --glass:rgba(255,255,255,.70); --glass-strong:rgba(255,255,255,.86);
      --ink:#17212b; --muted:#66727e; --line:rgba(114,133,151,.28);
      --teal:#0b7f86; --green:#3f7f5a; --amber:#b06218; --blue:#315f9f;
      font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Segoe UI",sans-serif;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; color:var(--ink); font-size:14px; letter-spacing:0; min-height:100vh;
      background:linear-gradient(135deg,#f7fbfb 0%,#e5eef4 42%,#f5f8f2 100%);
    }}
    header {{
      position:sticky; top:0; z-index:10;
      background:rgba(247,250,252,.76); border-bottom:1px solid rgba(255,255,255,.72);
      backdrop-filter:blur(22px) saturate(1.25); -webkit-backdrop-filter:blur(22px) saturate(1.25);
      box-shadow:0 10px 30px rgba(38,58,76,.08);
    }}
    .top {{ max-width:1440px; margin:0 auto; padding:16px 20px; display:flex; justify-content:space-between; gap:14px; align-items:center; }}
    h1 {{ margin:0; font-size:20px; font-weight:850; }}
    .meta {{ margin-top:4px; color:var(--muted); font-size:12px; }}
    main {{ max-width:1440px; margin:0 auto; padding:18px 20px 30px; }}
    .tabs {{
      display:inline-grid; grid-auto-flow:column; gap:2px; padding:3px;
      background:rgba(255,255,255,.46); border:1px solid rgba(255,255,255,.74); border-radius:8px;
      box-shadow:inset 0 1px 0 rgba(255,255,255,.9),0 12px 28px rgba(35,55,72,.08);
    }}
    button {{ font:inherit; }}
    .tabs button {{ border:0; background:transparent; padding:8px 12px; border-radius:6px; font-weight:800; color:var(--muted); cursor:pointer; transition:.18s ease; }}
    .tabs button:hover {{ color:var(--ink); }}
    .tabs button.active {{ background:var(--glass-strong); color:var(--ink); box-shadow:0 10px 24px rgba(48,70,90,.13),inset 0 1px 0 #fff; }}
    .kpis {{ display:grid; grid-template-columns:repeat(6,minmax(120px,1fr)); gap:10px; margin-bottom:14px; }}
    .kpi {{
      background:var(--glass); border:1px solid rgba(255,255,255,.78); border-radius:8px; padding:12px; min-height:76px;
      box-shadow:0 18px 40px rgba(38,58,76,.10),inset 0 1px 0 rgba(255,255,255,.82);
      backdrop-filter:blur(18px) saturate(1.18); -webkit-backdrop-filter:blur(18px) saturate(1.18);
    }}
    .label {{ color:var(--muted); font-size:12px; margin-bottom:8px; }}
    .value {{ font-weight:850; font-size:22px; }}
    .sub {{ color:var(--muted); font-size:12px; margin-top:5px; }}
    .panel {{
      background:var(--glass); border:1px solid rgba(255,255,255,.78); border-radius:8px; overflow:hidden; margin-bottom:14px;
      box-shadow:0 20px 45px rgba(39,57,74,.11),inset 0 1px 0 rgba(255,255,255,.86);
      backdrop-filter:blur(20px) saturate(1.18); -webkit-backdrop-filter:blur(20px) saturate(1.18);
    }}
    .panel-head {{ padding:12px 14px; border-bottom:1px solid var(--line); display:flex; justify-content:space-between; gap:10px; align-items:center; background:rgba(255,255,255,.34); }}
    .title {{ font-weight:850; }}
    .grid {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(340px,.75fr); gap:14px; }}
    .body {{ padding:12px 14px; }}
    .bars {{ display:grid; gap:9px; }}
    .bar {{ display:grid; grid-template-columns:minmax(90px,170px) 1fr 84px; gap:10px; align-items:center; }}
    .bar-name {{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:700; }}
    .track {{ height:10px; background:rgba(119,139,157,.18); border-radius:99px; overflow:hidden; box-shadow:inset 0 1px 3px rgba(36,54,72,.16); }}
    .fill {{ height:100%; background:linear-gradient(90deg,var(--teal),var(--green) 55%,var(--amber)); box-shadow:0 0 18px rgba(11,127,134,.28); }}
    .bar-size,.num {{ text-align:right; color:var(--muted); font-variant-numeric:tabular-nums; }}
    .toolbar {{ display:grid; grid-template-columns:minmax(240px,1.5fr) repeat(4,minmax(120px,.7fr)); gap:8px; padding:12px 14px; border-bottom:1px solid var(--line); background:rgba(255,255,255,.32); }}
    input,select {{
      min-height:36px; width:100%; border:1px solid rgba(104,122,141,.32); border-radius:6px; padding:7px 9px;
      background:rgba(255,255,255,.78); color:var(--ink); font:inherit; outline:none;
      box-shadow:inset 0 1px 0 rgba(255,255,255,.88);
    }}
    input:focus,select:focus {{ border-color:rgba(11,127,134,.62); box-shadow:0 0 0 3px rgba(11,127,134,.13); }}
    table {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
    th,td {{ padding:9px 10px; border-bottom:1px solid var(--line); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    th {{ color:var(--muted); font-size:12px; text-align:left; background:rgba(255,255,255,.52); position:sticky; top:0; backdrop-filter:blur(12px); }}
    tr:hover td {{ background:rgba(255,255,255,.42); }}
    .table-wrap {{ max-height:650px; overflow:auto; }}
    .chip {{ display:inline-flex; border:1px solid var(--line); border-radius:99px; padding:2px 8px; color:var(--muted); font-size:12px; font-weight:750; background:rgba(255,255,255,.45); }}
    .chip.teal {{ color:var(--teal); border-color:rgba(8,127,140,.25); background:rgba(8,127,140,.08); }}
    .path {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; color:var(--muted); font-size:12px; }}
    .link {{ color:var(--teal); text-decoration:none; font-weight:700; margin-right:8px; }}
    .pager {{ display:flex; justify-content:space-between; padding:11px 14px; color:var(--muted); }}
    .text-btn {{ border:1px solid var(--line); background:rgba(255,255,255,.68); border-radius:6px; padding:6px 10px; font-weight:750; cursor:pointer; }}
    .text-btn:hover {{ background:#fff; }}
    .view {{ display:none; }} .view.active {{ display:block; }}
    .dup {{ border:1px solid var(--line); border-radius:8px; margin-bottom:10px; overflow:hidden; background:rgba(255,255,255,.38); }}
    .dup-head {{ padding:10px 12px; border-bottom:1px solid var(--line); display:flex; justify-content:space-between; gap:10px; background:rgba(255,255,255,.30); }}
    .dup-files {{ padding:8px 12px 12px; display:grid; gap:6px; }}
    @media (max-width:1000px) {{ .kpis {{ grid-template-columns:repeat(3,1fr); }} .grid {{ grid-template-columns:1fr; }} .toolbar {{ grid-template-columns:1fr 1fr; }} }}
    @media (max-width:680px) {{ .top {{ display:block; }} .tabs {{ margin-top:10px; grid-template-columns:repeat(2,1fr); grid-auto-flow:row; width:100%; }} .kpis {{ grid-template-columns:repeat(2,1fr); }} .toolbar {{ grid-template-columns:1fr; }} .bar {{ grid-template-columns:1fr; }} .bar-size {{ text-align:left; }} }}
  </style>
</head>
<body>
  <header><div class="top"><div><h1>微信文件检查 Dashboard</h1><div class="meta" id="meta"></div></div><nav class="tabs"><button class="active" data-tab="overview">概览</button><button data-tab="files">文件</button><button data-tab="duplicates">重复</button><button data-tab="candidates">候选</button></nav></div></header>
  <main>
    <section class="kpis" id="kpis"></section>
    <section id="overview" class="view active"><div class="grid"><div class="panel"><div class="panel-head"><div class="title">类型分布</div></div><div class="body"><div class="bars" id="kindBars"></div></div></div><div class="panel"><div class="panel-head"><div class="title">月份分布</div></div><div class="body"><div class="bars" id="monthBars"></div></div></div></div><div class="panel"><div class="panel-head"><div class="title">最大文件</div></div><div class="table-wrap"><table id="topTable"></table></div></div></section>
    <section id="files" class="view"><div class="panel"><div class="toolbar"><input id="search" type="search" placeholder="搜索文件名或路径"><select id="kind"></select><select id="month"></select><select id="size"><option value="0">全部大小</option><option value="10485760">10MB+</option><option value="52428800">50MB+</option><option value="104857600">100MB+</option></select><select id="sort"><option value="size">大小降序</option><option value="mtime">修改时间降序</option><option value="month">月份降序</option><option value="name">名称升序</option></select></div><div class="table-wrap"><table id="fileTable"></table></div><div class="pager"><span id="count"></span><span><button class="text-btn" id="prev">上一页</button> <button class="text-btn" id="next">下一页</button></span></div></div></section>
    <section id="duplicates" class="view"><div class="panel"><div class="panel-head"><div class="title">重复大文件</div><div id="dupMeta" class="meta"></div></div><div class="body" id="dupList"></div></div></section>
    <section id="candidates" class="view"><div class="panel"><div class="panel-head"><div class="title">旧文件候选桶</div><div class="meta">只读统计，不执行删除</div></div><div class="table-wrap"><table id="candidateTable"></table></div></div></section>
  </main>
  <script>const DATA={data};</script>
  <script>
    const state={{page:1,pageSize:120}};
    const fmt=new Intl.NumberFormat('zh-CN');
    const $=id=>document.getElementById(id);
    const labelMap={{msg_file:'接收文件',msg_video:'视频',msg_attach:'附件碎片',account_cache:'账号缓存'}};
    const zh=v=>labelMap[v]||v;
    const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;","\\\"":"&quot;","'":"&#39;"}}[c]));
    const href=p=>'file://'+encodeURI(p).replace(/#/g,'%23');
    function table(el,heads,rows,widths=[]){{const cg=widths.length?'<colgroup>'+widths.map(w=>`<col style="width:${{w}}">`).join('')+'</colgroup>':'';el.innerHTML=cg+'<thead><tr>'+heads.map(h=>`<th>${{h}}</th>`).join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(c=>`<td>${{c}}</td>`).join('')+'</tr>').join('')+'</tbody>';}}
    function bars(el,rows,n){{const top=rows.slice(0,n),max=Math.max(...top.map(r=>r.size_bytes),1);el.innerHTML=top.map(r=>`<div class="bar"><div class="bar-name" title="${{esc(r.name)}}">${{esc(r.name)}}</div><div class="track"><div class="fill" style="width:${{Math.max(2,r.size_bytes/max*100)}}%"></div></div><div class="bar-size">${{r.size}}</div></div>`).join('');}}
    function actions(p){{return `<a class="link" href="${{href(p)}}">打开</a><a class="link" href="#" onclick="navigator.clipboard&&navigator.clipboard.writeText(${{JSON.stringify(p)}});return false;">复制</a>`;}}
    function init(){{$('meta').textContent=`生成 ${{DATA.generated_at}} · ${{DATA.xwechat_root}}`; $('kpis').innerHTML=[['数据目录',DATA.xwechat_root_size],['可见文件',DATA.summary.total_size,fmt.format(DATA.summary.file_count)+' 个'],['100MB+ 文件',fmt.format(DATA.summary.large_file_count)],['重复组',fmt.format(DATA.summary.duplicate_group_count),DATA.summary.duplicate_potential_savings],['候选桶',fmt.format(DATA.candidates.length)],['账号',fmt.format(DATA.accounts.length)]].map(i=>`<div class="kpi"><div class="label">${{i[0]}}</div><div class="value">${{i[1]}}</div>${{i[2]?`<div class="sub">${{i[2]}}</div>`:''}}</div>`).join('');bars($('kindBars'),DATA.summary.by_kind,12);bars($('monthBars'),DATA.summary.by_month,18);renderTop();initFilters();renderFiles();renderDup();renderCandidates();document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));b.classList.add('active');$(b.dataset.tab).classList.add('active');}});}}
    function renderTop(){{table($('topTable'),['文件','来源','月份','大小','操作'],DATA.top_files.slice(0,60).map(r=>[`<span title="${{esc(r.path)}}">${{esc(r.name)}}</span>`,esc(r.source),esc(r.month),`<span class="num">${{r.size}}</span>`,actions(r.path)]),['44%','12%','10%','12%','110px']);}}
    function initFilters(){{$('kind').innerHTML='<option value="">全部类型</option>'+DATA.summary.by_kind.map(r=>`<option>${{esc(r.name)}}</option>`).join('');$('month').innerHTML='<option value="">全部月份</option>'+DATA.summary.by_month.map(r=>r.name).sort().reverse().map(m=>`<option>${{esc(m)}}</option>`).join('');['search','kind','month','size','sort'].forEach(id=>$(id).oninput=()=>{{state.page=1;renderFiles();}});$('prev').onclick=()=>{{state.page=Math.max(1,state.page-1);renderFiles();}};$('next').onclick=()=>{{state.page+=1;renderFiles();}};}}
    function filtered(){{let rows=DATA.files.filter(r=>(!$('kind').value||r.kind===$('kind').value)&&(!$('month').value||r.month===$('month').value)&&r.size_bytes>=Number($('size').value)&&(!$('search').value||(r.name+' '+r.path).toLowerCase().includes($('search').value.toLowerCase())));const s=$('sort').value,coll=new Intl.Collator('zh-CN',{{numeric:true}});rows.sort((a,b)=>s==='size'?b.size_bytes-a.size_bytes:s==='mtime'?String(b.mtime).localeCompare(String(a.mtime)):s==='month'?String(b.month).localeCompare(String(a.month)):coll.compare(a.name,b.name));return rows;}}
    function renderFiles(){{const rows=filtered(),pages=Math.max(1,Math.ceil(rows.length/state.pageSize));state.page=Math.min(state.page,pages);const page=rows.slice((state.page-1)*state.pageSize,state.page*state.pageSize);table($('fileTable'),['文件','类型','月份','大小','路径','操作'],page.map(r=>[`<span title="${{esc(r.name)}}">${{esc(r.name)}}</span>`,`<span class="chip teal">${{esc(r.kind)}}</span>`,esc(r.month),`<span class="num">${{r.size}}</span>`,`<span class="path" title="${{esc(r.path)}}">${{esc(r.path)}}</span>`,actions(r.path)]),['26%','10%','9%','9%','36%','110px']);$('count').textContent=`${{fmt.format(rows.length)}} 个结果 · 第 ${{state.page}} / ${{pages}} 页`;$('prev').disabled=state.page<=1;$('next').disabled=state.page>=pages;}}
    function renderDup(){{$('dupMeta').textContent=`${{DATA.duplicates.length}} 组 · 理论节省 ${{DATA.summary.duplicate_potential_savings}}`;$('dupList').innerHTML=DATA.duplicates.map((g,i)=>`<article class="dup"><div class="dup-head"><strong>#${{i+1}} · ${{g.potential_savings}}</strong><span class="chip">${{g.count}} 份</span></div><div class="dup-files">${{g.files.map(f=>`<div><span class="chip">${{esc(f.month)}}</span> <span class="path">${{esc(f.path)}}</span> ${{actions(f.path)}}</div>`).join('')}}</div></article>`).join('');}}
    function renderCandidates(){{table($('candidateTable'),['类别','账号','月份','大小','说明','路径'],DATA.candidates.slice(0,300).map(r=>[`<span class="chip">${{esc(zh(r.category))}}</span>`,esc(r.account),esc(r.month),`<span class="num">${{r.size}}</span>`,esc(r.note),`<span class="path">${{esc(r.path)}}</span>`]),['12%','18%','8%','10%','22%','30%']);}}
    init();
  </script>
</body>
</html>"""


def write_dashboard(scan_result, output_path):
    output_path = Path(output_path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_dashboard_html(scan_result), encoding="utf-8")
    return str(output_path)


def render_markdown_summary(scan_result):
    lines = [
        "# Clean My WeChat macOS 扫描报告",
        "",
        f"- 生成时间：{scan_result['generated_at']}",
        f"- 数据目录：`{scan_result['xwechat_root']}`",
        f"- 目录占用：{scan_result['xwechat_root_size']}",
        f"- 已索引可见文件：{scan_result['summary']['file_count']}（{scan_result['summary']['total_size']}）",
        f"- 重复大文件组：{scan_result['summary']['duplicate_group_count']}（理论可节省 {scan_result['summary']['duplicate_potential_savings']}）",
        "",
        "## 最大文件类型",
        "",
        "| 类型 | 数量 | 大小 |",
        "| --- | ---: | ---: |",
    ]
    for row in scan_result["summary"]["by_kind"][:20]:
        lines.append(f"| {row['name']} | {row['count']} | {row['size']} |")
    lines.extend(["", "## 最大月份", "", "| 月份 | 数量 | 大小 |", "| --- | ---: | ---: |"])
    for row in scan_result["summary"]["by_month"][:30]:
        lines.append(f"| {row['name']} | {row['count']} | {row['size']} |")
    lines.extend(["", "## 旧文件候选桶", "", "| 类别 | 账号 | 月份 | 大小 | 说明 |", "| --- | --- | --- | ---: | --- |"])
    for row in scan_result["candidates"][:80]:
        lines.append(f"| {row['category']} | {row['account']} | {row['month']} | {row['size']} | {row['note']} |")
    return "\n".join(lines)


def write_markdown_summary(scan_result, output_path):
    output_path = Path(output_path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_summary(scan_result), encoding="utf-8")
    return str(output_path)
