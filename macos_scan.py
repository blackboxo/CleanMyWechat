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
    parser = argparse.ArgumentParser(description="Read-only macOS WeChat scanner and dashboard generator.")
    parser.add_argument("--source", default=str(default_xwechat_root()), help="Path to macOS xwechat_files.")
    parser.add_argument("--output", default=str(Path.home() / "Documents/CleanMyWechat-macOS"), help="Output folder.")
    parser.add_argument("--cutoff-month", default=DEFAULT_CUTOFF_MONTH, help="YYYY-MM; earlier months are shown as candidates.")
    parser.add_argument("--no-view", action="store_true", help="Skip symlink organized view generation.")
    return parser.parse_args()


def main():
    args = parse_args()
    output = Path(args.output).expanduser()
    scan = scan_macos_wechat(args.source, cutoff_month=args.cutoff_month)
    reports_dir = output / "reports"
    dashboard_path = output / "dashboard/wechat_dashboard.html"
    summary_path = reports_dir / "macos_wechat_summary.md"

    outputs = write_scan_outputs(scan, reports_dir)
    write_markdown_summary(scan, summary_path)
    write_dashboard(scan, dashboard_path)

    view_result = None
    if not args.no_view:
        view_result = create_symlink_view(scan, output / "organized_view")

    print(f"Dashboard: {dashboard_path}")
    print(f"Summary: {summary_path}")
    print(f"JSON: {outputs['json']}")
    print(f"Files indexed: {scan['summary']['file_count']}")
    print(f"Duplicate groups: {scan['summary']['duplicate_group_count']}")
    print(f"Potential duplicate savings: {scan['summary']['duplicate_potential_savings']}")
    if view_result:
        print(f"Organized view: {view_result['root']}")


if __name__ == "__main__":
    main()
