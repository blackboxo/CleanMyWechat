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
    ]


def discover_xwechat_roots(home=None):
    return [path for path in common_xwechat_roots(home) if path.exists()]


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
    return name.startswith("wxid_") and bool({"msg", "cache", "db_storage"} & names)


def discover_accounts(xwechat_root):
    root = Path(xwechat_root).expanduser()
    if not root.exists():
        return []
    return sorted([path for path in root.iterdir() if is_account_dir(path)], key=lambda path: path.name)


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


def collect_file_records(account, source_name, root):
    records = []
    for path in iter_files(root):
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
    return records


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duplicate_groups(roots, threshold=DEFAULT_DUPLICATE_THRESHOLD):
    by_size = defaultdict(list)
    for root in roots:
        for path in iter_files(root):
            size = file_size(path)
            if size >= threshold:
                by_size[size].append(path)

    groups = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash = defaultdict(list)
        for path in paths:
            try:
                by_hash[sha256(path)].append(path)
            except OSError:
                continue
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


def scan_macos_wechat(xwechat_root=None, cutoff_month=DEFAULT_CUTOFF_MONTH, duplicate_threshold=DEFAULT_DUPLICATE_THRESHOLD):
    root = Path(xwechat_root).expanduser() if xwechat_root else default_xwechat_root()
    accounts = discover_accounts(root)
    account_rows = []
    candidates = []
    records = []
    duplicate_roots = []

    for account in accounts:
        sections = {}
        for child in account.iterdir():
            if child.is_dir():
                sections[child.name] = tree_size(child)

        msg_file = account / "msg/file"
        msg_video = account / "msg/video"
        msg_attach = account / "msg/attach"
        cache = account / "cache"
        duplicate_roots.extend([msg_file, msg_video, msg_attach])

        records.extend(collect_file_records(account, "msg/file", msg_file))
        records.extend(collect_file_records(account, "msg/video", msg_video))

        months = {
            "msg_file": month_dir_sizes(msg_file),
            "msg_video": month_dir_sizes(msg_video),
            "msg_attach": attach_month_summary(msg_attach),
            "account_cache": month_dir_sizes(cache),
        }

        for category, month_sizes in months.items():
            for month, size in month_sizes.items():
                if month < cutoff_month:
                    base_path = {
                        "msg_file": msg_file / month,
                        "msg_video": msg_video / month,
                        "msg_attach": msg_attach,
                        "account_cache": cache / month,
                    }[category]
                    note = {
                        "msg_file": "user-visible received files",
                        "msg_video": "user-visible videos",
                        "msg_attach": "images/audio/attachment fragments grouped by contact hash",
                        "account_cache": "account month cache",
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

    top_files = sorted([asdict(record) for record in records], key=lambda row: row["size_bytes"], reverse=True)[:200]
    duplicate_data = duplicate_groups(duplicate_roots, threshold=duplicate_threshold)
    duplicate_savings = sum(group["potential_savings_bytes"] for group in duplicate_data)
    summary = summarize_records(records)
    summary["duplicate_group_count"] = len(duplicate_data)
    summary["duplicate_potential_savings_bytes"] = duplicate_savings
    summary["duplicate_potential_savings"] = human_size(duplicate_savings)

    root_size = tree_size(root)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "platform": "macOS",
        "xwechat_root": str(root),
        "xwechat_root_exists": root.exists(),
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
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
                "# Clean My WeChat macOS Organized View",
                "",
                "This folder only contains symlinks to original WeChat files.",
                "Deleting a symlink here does not delete the original file.",
                "",
                f"Generated: {datetime.now().isoformat(timespec='seconds')}",
                f"Source: {scan_result['xwechat_root']}",
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
  <title>Clean My WeChat macOS Dashboard</title>
  <style>
    :root {{
      --bg:#f5f6f7; --panel:#fff; --ink:#20242a; --muted:#66717d;
      --line:#d8dde3; --teal:#087f8c; --green:#3f7d4a; --amber:#a85d00;
      font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font-size:14px; letter-spacing:0; }}
    header {{ position:sticky; top:0; z-index:10; background:var(--panel); border-bottom:1px solid var(--line); }}
    .top {{ max-width:1440px; margin:0 auto; padding:14px 20px; display:flex; justify-content:space-between; gap:14px; align-items:center; }}
    h1 {{ margin:0; font-size:20px; }}
    .meta {{ margin-top:4px; color:var(--muted); font-size:12px; }}
    main {{ max-width:1440px; margin:0 auto; padding:18px 20px 30px; }}
    .tabs {{ display:inline-grid; grid-auto-flow:column; gap:2px; padding:3px; background:#edf1f4; border:1px solid var(--line); border-radius:8px; }}
    button {{ font:inherit; }}
    .tabs button {{ border:0; background:transparent; padding:8px 12px; border-radius:6px; font-weight:700; color:var(--muted); cursor:pointer; }}
    .tabs button.active {{ background:#fff; color:var(--ink); box-shadow:0 1px 6px rgba(0,0,0,.1); }}
    .kpis {{ display:grid; grid-template-columns:repeat(6,minmax(120px,1fr)); gap:10px; margin-bottom:14px; }}
    .kpi {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:12px; min-height:76px; }}
    .label {{ color:var(--muted); font-size:12px; margin-bottom:8px; }}
    .value {{ font-weight:800; font-size:22px; }}
    .sub {{ color:var(--muted); font-size:12px; margin-top:5px; }}
    .panel {{ background:#fff; border:1px solid var(--line); border-radius:8px; overflow:hidden; margin-bottom:14px; }}
    .panel-head {{ padding:12px 14px; border-bottom:1px solid var(--line); display:flex; justify-content:space-between; gap:10px; align-items:center; }}
    .title {{ font-weight:800; }}
    .grid {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(340px,.75fr); gap:14px; }}
    .body {{ padding:12px 14px; }}
    .bars {{ display:grid; gap:9px; }}
    .bar {{ display:grid; grid-template-columns:minmax(90px,170px) 1fr 84px; gap:10px; align-items:center; }}
    .bar-name {{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:700; }}
    .track {{ height:10px; background:#edf0f2; border-radius:99px; overflow:hidden; }}
    .fill {{ height:100%; background:linear-gradient(90deg,var(--teal),var(--green)); }}
    .bar-size,.num {{ text-align:right; color:var(--muted); font-variant-numeric:tabular-nums; }}
    .toolbar {{ display:grid; grid-template-columns:minmax(240px,1.5fr) repeat(4,minmax(120px,.7fr)); gap:8px; padding:12px 14px; border-bottom:1px solid var(--line); background:#fbfcfd; }}
    input,select {{ min-height:36px; width:100%; border:1px solid #aeb7c2; border-radius:6px; padding:7px 9px; background:#fff; color:var(--ink); font:inherit; }}
    table {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
    th,td {{ padding:9px 10px; border-bottom:1px solid var(--line); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    th {{ color:var(--muted); font-size:12px; text-align:left; background:#fbfcfd; position:sticky; top:0; }}
    .table-wrap {{ max-height:650px; overflow:auto; }}
    .chip {{ display:inline-flex; border:1px solid var(--line); border-radius:99px; padding:2px 8px; color:var(--muted); font-size:12px; font-weight:700; }}
    .chip.teal {{ color:var(--teal); border-color:rgba(8,127,140,.25); background:rgba(8,127,140,.08); }}
    .path {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; color:var(--muted); font-size:12px; }}
    .link {{ color:var(--teal); text-decoration:none; font-weight:700; margin-right:8px; }}
    .pager {{ display:flex; justify-content:space-between; padding:11px 14px; color:var(--muted); }}
    .text-btn {{ border:1px solid var(--line); background:#fff; border-radius:6px; padding:6px 10px; font-weight:700; cursor:pointer; }}
    .view {{ display:none; }} .view.active {{ display:block; }}
    .dup {{ border:1px solid var(--line); border-radius:8px; margin-bottom:10px; overflow:hidden; }}
    .dup-head {{ padding:10px 12px; border-bottom:1px solid var(--line); display:flex; justify-content:space-between; gap:10px; }}
    .dup-files {{ padding:8px 12px 12px; display:grid; gap:6px; }}
    @media (max-width:1000px) {{ .kpis {{ grid-template-columns:repeat(3,1fr); }} .grid {{ grid-template-columns:1fr; }} .toolbar {{ grid-template-columns:1fr 1fr; }} }}
    @media (max-width:680px) {{ .top {{ display:block; }} .tabs {{ margin-top:10px; grid-template-columns:repeat(2,1fr); grid-auto-flow:row; width:100%; }} .kpis {{ grid-template-columns:repeat(2,1fr); }} .toolbar {{ grid-template-columns:1fr; }} .bar {{ grid-template-columns:1fr; }} .bar-size {{ text-align:left; }} }}
  </style>
</head>
<body>
  <header><div class="top"><div><h1>Clean My WeChat macOS Dashboard</h1><div class="meta" id="meta"></div></div><nav class="tabs"><button class="active" data-tab="overview">概览</button><button data-tab="files">文件</button><button data-tab="duplicates">重复</button><button data-tab="candidates">候选</button></nav></div></header>
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
    const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;","\\\"":"&quot;","'":"&#39;"}}[c]));
    const href=p=>'file://'+encodeURI(p).replace(/#/g,'%23');
    function table(el,heads,rows,widths=[]){{const cg=widths.length?'<colgroup>'+widths.map(w=>`<col style="width:${{w}}">`).join('')+'</colgroup>':'';el.innerHTML=cg+'<thead><tr>'+heads.map(h=>`<th>${{h}}</th>`).join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(c=>`<td>${{c}}</td>`).join('')+'</tr>').join('')+'</tbody>';}}
    function bars(el,rows,n){{const top=rows.slice(0,n),max=Math.max(...top.map(r=>r.size_bytes),1);el.innerHTML=top.map(r=>`<div class="bar"><div class="bar-name" title="${{esc(r.name)}}">${{esc(r.name)}}</div><div class="track"><div class="fill" style="width:${{Math.max(2,r.size_bytes/max*100)}}%"></div></div><div class="bar-size">${{r.size}}</div></div>`).join('');}}
    function actions(p){{return `<a class="link" href="${{href(p)}}">打开</a><a class="link" href="#" onclick="navigator.clipboard&&navigator.clipboard.writeText(${{JSON.stringify(p)}});return false;">复制</a>`;}}
    function init(){{$('meta').textContent=`生成 ${{DATA.generated_at}} · ${{DATA.xwechat_root}}`; $('kpis').innerHTML=[['xwechat_files',DATA.xwechat_root_size],['可见文件',DATA.summary.total_size,fmt.format(DATA.summary.file_count)+' 个'],['100MB+ 文件',fmt.format(DATA.summary.large_file_count)],['重复组',fmt.format(DATA.summary.duplicate_group_count),DATA.summary.duplicate_potential_savings],['候选桶',fmt.format(DATA.candidates.length)],['账号',fmt.format(DATA.accounts.length)]].map(i=>`<div class="kpi"><div class="label">${{i[0]}}</div><div class="value">${{i[1]}}</div>${{i[2]?`<div class="sub">${{i[2]}}</div>`:''}}</div>`).join('');bars($('kindBars'),DATA.summary.by_kind,12);bars($('monthBars'),DATA.summary.by_month,18);renderTop();initFilters();renderFiles();renderDup();renderCandidates();document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));b.classList.add('active');$(b.dataset.tab).classList.add('active');}});}}
    function renderTop(){{table($('topTable'),['文件','来源','月份','大小','操作'],DATA.top_files.slice(0,60).map(r=>[`<span title="${{esc(r.path)}}">${{esc(r.name)}}</span>`,esc(r.source),esc(r.month),`<span class="num">${{r.size}}</span>`,actions(r.path)]),['44%','12%','10%','12%','110px']);}}
    function initFilters(){{$('kind').innerHTML='<option value="">全部类型</option>'+DATA.summary.by_kind.map(r=>`<option>${{esc(r.name)}}</option>`).join('');$('month').innerHTML='<option value="">全部月份</option>'+DATA.summary.by_month.map(r=>r.name).sort().reverse().map(m=>`<option>${{esc(m)}}</option>`).join('');['search','kind','month','size','sort'].forEach(id=>$(id).oninput=()=>{{state.page=1;renderFiles();}});$('prev').onclick=()=>{{state.page=Math.max(1,state.page-1);renderFiles();}};$('next').onclick=()=>{{state.page+=1;renderFiles();}};}}
    function filtered(){{let rows=DATA.files.filter(r=>(!$('kind').value||r.kind===$('kind').value)&&(!$('month').value||r.month===$('month').value)&&r.size_bytes>=Number($('size').value)&&(!$('search').value||(r.name+' '+r.path).toLowerCase().includes($('search').value.toLowerCase())));const s=$('sort').value,coll=new Intl.Collator('zh-CN',{{numeric:true}});rows.sort((a,b)=>s==='size'?b.size_bytes-a.size_bytes:s==='mtime'?String(b.mtime).localeCompare(String(a.mtime)):s==='month'?String(b.month).localeCompare(String(a.month)):coll.compare(a.name,b.name));return rows;}}
    function renderFiles(){{const rows=filtered(),pages=Math.max(1,Math.ceil(rows.length/state.pageSize));state.page=Math.min(state.page,pages);const page=rows.slice((state.page-1)*state.pageSize,state.page*state.pageSize);table($('fileTable'),['文件','类型','月份','大小','路径','操作'],page.map(r=>[`<span title="${{esc(r.name)}}">${{esc(r.name)}}</span>`,`<span class="chip teal">${{esc(r.kind)}}</span>`,esc(r.month),`<span class="num">${{r.size}}</span>`,`<span class="path" title="${{esc(r.path)}}">${{esc(r.path)}}</span>`,actions(r.path)]),['26%','10%','9%','9%','36%','110px']);$('count').textContent=`${{fmt.format(rows.length)}} 个结果 · 第 ${{state.page}} / ${{pages}} 页`;$('prev').disabled=state.page<=1;$('next').disabled=state.page>=pages;}}
    function renderDup(){{$('dupMeta').textContent=`${{DATA.duplicates.length}} 组 · 理论节省 ${{DATA.summary.duplicate_potential_savings}}`;$('dupList').innerHTML=DATA.duplicates.map((g,i)=>`<article class="dup"><div class="dup-head"><strong>#${{i+1}} · ${{g.potential_savings}}</strong><span class="chip">${{g.count}} 份</span></div><div class="dup-files">${{g.files.map(f=>`<div><span class="chip">${{esc(f.month)}}</span> <span class="path">${{esc(f.path)}}</span> ${{actions(f.path)}}</div>`).join('')}}</div></article>`).join('');}}
    function renderCandidates(){{table($('candidateTable'),['类别','账号','月份','大小','说明','路径'],DATA.candidates.slice(0,300).map(r=>[`<span class="chip">${{esc(r.category)}}</span>`,esc(r.account),esc(r.month),`<span class="num">${{r.size}}</span>`,esc(r.note),`<span class="path">${{esc(r.path)}}</span>`]),['12%','18%','8%','10%','22%','30%']);}}
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
        "# Clean My WeChat macOS Scan Report",
        "",
        f"- Generated: {scan_result['generated_at']}",
        f"- Source: `{scan_result['xwechat_root']}`",
        f"- Source size: {scan_result['xwechat_root_size']}",
        f"- Visible files indexed: {scan_result['summary']['file_count']} ({scan_result['summary']['total_size']})",
        f"- Duplicate groups: {scan_result['summary']['duplicate_group_count']} ({scan_result['summary']['duplicate_potential_savings']} potential savings)",
        "",
        "## Biggest Kinds",
        "",
        "| Kind | Count | Size |",
        "| --- | ---: | ---: |",
    ]
    for row in scan_result["summary"]["by_kind"][:20]:
        lines.append(f"| {row['name']} | {row['count']} | {row['size']} |")
    lines.extend(["", "## Biggest Months", "", "| Month | Count | Size |", "| --- | ---: | ---: |"])
    for row in scan_result["summary"]["by_month"][:30]:
        lines.append(f"| {row['name']} | {row['count']} | {row['size']} |")
    lines.extend(["", "## Candidate Buckets", "", "| Category | Account | Month | Size | Note |", "| --- | --- | --- | ---: | --- |"])
    for row in scan_result["candidates"][:80]:
        lines.append(f"| {row['category']} | {row['account']} | {row['month']} | {row['size']} | {row['note']} |")
    return "\n".join(lines)


def write_markdown_summary(scan_result, output_path):
    output_path = Path(output_path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_summary(scan_result), encoding="utf-8")
    return str(output_path)
