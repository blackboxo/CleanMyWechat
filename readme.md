# Clean My PC WeChat

![](https://markdown-pic-blackboxo.oss-cn-shanghai.aliyuncs.com/banner.png)

[![](https://img.shields.io/badge/platform-win64-lightgrey)](https://github.com/blackboxo/AutoDeleteFileOnPCWechat/releases) [![](https://img.shields.io/github/v/release/blackboxo/AutoDeleteFileOnPCWechat)](https://github.com/blackboxo/AutoDeleteFileOnPCWechat/releases) [![](https://img.shields.io/github/downloads/blackboxo/AutoDeleteFileOnPCWechat/total)](https://github.com/blackboxo/AutoDeleteFileOnPCWechat/releases)

<a href="https://hellogithub.com/repository/372422c3479e496aabd39ee17d56b5ba" target="_blank"><img src="https://api.hellogithub.com/v1/widgets/recommend.svg?rid=372422c3479e496aabd39ee17d56b5ba&claim_uid=Nyem9zKIlpfGH2U" alt="Featured｜HelloGitHub" style="width: 250px; height: 54px;" width="250" height="54" /></a>

自动删除 PC 端微信自动下载的大量文件、视频、图片等数据内容，解放一年几十 G 的空间占用。

该工具不会删除文字的聊天记录，请放心使用。请给个 **Star** 吧，非常感谢！

**现已经支持 Windows 系统中的所有微信版本，包含最新版的微信 4.0+ 和企业微信。**

> macOS 支持仍处于实验阶段：当前提供只读扫描、统计 Dashboard、重复大文件检查和符号链接整理视图，不会移动、删除或重命名微信原文件。

[国内地址 - 点击下载](
https://wwbie.lanzoue.com/iHgXp3ql84ng)

[Github Release - 点击下载](
https://github.com/blackboxo/CleanMyWechat/releases/download/v2.1/CleanMyWechat.zip)

## 特性
1. 自动识别所有微信及企业微信账号；
2. 自由设置想要删除的文件类型，包括文件、图片、视频；
3. 自由设置需要删除的文件的距离时间，默认 365 天；
4. 删除后的文件放置在回收站中，检查后自行清空，防止删错需要的文件；
5. 支持定期自动清理；

## macOS 实验版

macOS 微信 4.x 的本地文件通常位于：

```text
~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files
```

本仓库提供一个独立的 macOS 只读入口，帮助先看清楚文件、月份、类型、重复大文件和候选清理桶，再决定是否人工归档。

安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

运行图形界面：

```bash
python3 macos_app.py
```

或直接生成 Dashboard：

```bash
python3 macos_scan.py
```

本地打包为 `.app`：

```bash
pyinstaller --windowed --name CleanMyWechat-macOS macos_app.py
```

生成结果默认位于：

```text
~/Documents/CleanMyWechat-macOS
```

包含：

- `dashboard/wechat_dashboard.html`：本地静态 Dashboard，可按类型、月份、大小搜索和筛选；
- `organized_view/`：按月份、类型、大文件创建的符号链接视图；
- `reports/`：JSON、CSV 和 Markdown 扫描报告。

安全说明：

- 默认不删除、不移动、不改名任何微信文件；
- `organized_view/` 只包含符号链接，删除链接不会删除微信原文件；
- `db_storage`、`config`、`business/favorite` 等运行数据只统计，不纳入整理视图；
- 如需释放空间，建议先从 Dashboard 中确认大文件和重复文件，再手工归档。

## 运行截图

![Clean My Wechat 首页](images/README-merge.png)

## 微信现状

下载两年时间，微信一个软件就占用多达 33.5 G 存储空间。其中大部分都是与自己无关的各大群聊中的文件、视频、图片等内容，且很久以前的文件仍旧存在电脑中。

![](images/wechatdisk.png)

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=blackboxo/CleanMyWechat&type=Date)](https://star-history.com/#blackboxo/CleanMyWechat&Date)
