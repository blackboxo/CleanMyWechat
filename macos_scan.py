import argparse
from pathlib import Path

from utils.macos_wechat import (
    DEFAULT_CUTOFF_MONTH,
    create_symlink_view,
    default_xwechat_root,
    scan_macos_wechat,
    write_dashboard,
    write_markdown_summary,
    write_scan_outputs,
)


def parse_args():
    parser = argparse.ArgumentParser(description="只读扫描 macOS 微信文件，并生成本地 Dashboard。")
    parser.add_argument("--source", default=str(default_xwechat_root()), help="macOS xwechat_files 路径。")
    parser.add_argument("--output", default=str(Path.home() / "Documents/CleanMyWechat-macOS"), help="输出目录。")
    parser.add_argument("--cutoff-month", default=DEFAULT_CUTOFF_MONTH, help="YYYY-MM；早于该月份的内容会列为候选桶。")
    parser.add_argument("--no-view", action="store_true", help="跳过符号链接整理视图。")
    parser.add_argument("--quiet", action="store_true", help="不显示扫描进度。")
    return parser.parse_args()


def print_progress(event):
    percent = min(90, max(1, 1 + int(event["percent"] * 0.89)))
    print(f"[{percent:3d}%] {event['message']}", flush=True)


def main():
    args = parse_args()
    output = Path(args.output).expanduser()
    scan = scan_macos_wechat(args.source, cutoff_month=args.cutoff_month, progress_callback=None if args.quiet else print_progress)
    reports_dir = output / "reports"
    dashboard_path = output / "dashboard/wechat_dashboard.html"
    summary_path = reports_dir / "macos_wechat_summary.md"

    if not args.quiet:
        print("[ 92%] 正在写入报告", flush=True)
    outputs = write_scan_outputs(scan, reports_dir)
    write_markdown_summary(scan, summary_path)

    if not args.quiet:
        print("[ 95%] 正在生成 Dashboard", flush=True)
    write_dashboard(scan, dashboard_path)

    view_result = None
    if not args.no_view:
        if not args.quiet:
            print("[ 98%] 正在创建整理视图", flush=True)
        view_result = create_symlink_view(scan, output / "organized_view")

    if not args.quiet:
        print("[100%] 完成", flush=True)
    print(f"Dashboard：{dashboard_path}")
    print(f"摘要：{summary_path}")
    print(f"JSON：{outputs['json']}")
    print(f"已索引文件：{scan['summary']['file_count']}")
    print(f"重复大文件组：{scan['summary']['duplicate_group_count']}")
    print(f"理论重复节省：{scan['summary']['duplicate_potential_savings']}")
    if view_result:
        print(f"整理视图：{view_result['root']}")


if __name__ == "__main__":
    main()
