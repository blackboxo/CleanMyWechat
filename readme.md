# Clean My PC Wechat

![](https://markdown-pic-blackboxo.oss-cn-shanghai.aliyuncs.com/banner.png)

[![](https://img.shields.io/badge/platform-win64-lightgrey)](https://github.com/blackboxo/AutoDeleteFileOnPCWechat/releases) [![](https://img.shields.io/github/v/release/blackboxo/AutoDeleteFileOnPCWechat)](https://github.com/blackboxo/AutoDeleteFileOnPCWechat/releases) [![](https://img.shields.io/github/downloads/blackboxo/AutoDeleteFileOnPCWechat/total)](https://github.com/blackboxo/AutoDeleteFileOnPCWechat/releases)

<a href="https://hellogithub.com/repository/372422c3479e496aabd39ee17d56b5ba" target="_blank"><img src="https://api.hellogithub.com/v1/widgets/recommend.svg?rid=372422c3479e496aabd39ee17d56b5ba&claim_uid=Nyem9zKIlpfGH2U" alt="Featured｜HelloGitHub" style="width: 250px; height: 54px;" width="250" height="54" /></a>

自动删除 PC 端微信自动下载的大量文件、视频、图片等数据内容，解放一年几十 G 的空间占用。

该工具不会删除文字的聊天记录，请放心使用。请给个 **Star** 吧，非常感谢！

**现已经支持 Windows 系统中的所有微信版本。**

[国内地址 - 点击下载](
https://wwvs.lanzouj.com/is77n0yap4dc)

[Github Release - 点击下载](
https://github.com/blackboxo/CleanMyWechat/releases/download/v2.1/CleanMyWechat.zip)

**碰到无法清理的，请记得勾选第一个选项，勾选后才会清理该账号下的内容。**

## 特性
1. 自动识别微信账号，支持用户选择自定义路径；
2. 同时管理多个账号，保留配置参数，打开即用；
3. 自由设置想要删除的文件类型，包括图片类缓存、文件、图片、视频；
4. 自由设置需要删除的文件的距离时间，默认 365 天；
5. 删除后的文件放置在回收站中，检查后自行清空，防止删错需要的文件；

## 运行截图

![](https://markdown-pic-blackboxo.oss-cn-shanghai.aliyuncs.com/20200929151623.jpg)

## 微信现状

下载两年时间，微信一个软件就占用多达 33.5 G 存储空间。其中大部分都是与自己无关的各大群聊中的文件、视频、图片等内容，且很久以前的文件仍旧存在电脑中。

![](https://markdown-pic-blackboxo.oss-cn-shanghai.aliyuncs.com/20200213142805.png)

## 待改进

欢迎 PR！

- [ ] Mac 版本的开发
- [x] 增加企业微信的支持
- [ ] Windows XP/7 系统的支持

### 企业微信支持说明

当前版本已尝试增加企业微信（WXWork）基础支持，主要包括：

- 自动识别常见企业微信目录，例如 `Documents/WXWork`、`%APPDATA%/Tencent/WXWork`、`%LOCALAPPDATA%/Tencent/WXWork`
- 在设置里手动选择 `WXWork` 文件夹后，可以识别企业微信账号目录
- 支持扫描企业微信常见的 `Cache`、`File`、`Files`、`Document`、`Image`、`Images`、`Video`、`Videos` 等目录
- 系统缓存部分会额外扫描企业微信系统区下明确的 `log`、`temp`、`Cache` 等安全目录
- 仍然保留安全跳过规则：`.dll`、`.exe`、`.db`、`.pyd`、`.pak` 等程序组件和数据库文件不会清理

使用时如果是普通微信，继续选择 `WeChat Files`；如果是企业微信，请在设置中选择 `WXWork` 文件夹。

其他需求详见 Issue

## 打包 EXE 方式

```Shell
pip install -r requirements.txt
pyinstaller -F -i images/icon.ico -w main.py
cp -r images dist/
./dist/main.exe
```

## 致谢

[@mylittlefox](https://www.mylittlefox.art)：图标及 Banner 设计

[@Gears](https://refun.eu.org)：提供微信 for Windows 版本的文件目录树及测试支持

@SongJee：版本 1.1 的主要开发者，增加进度条，支持多个微信版本，自动识别路径

[@LenmoisLemon](https://github.com/LenmoisLemon)：版本 2.0 的主要开发者，全新 UI 设计，增加多用户配置

[@Louhwz](https://github.com/Louhwz)：版本 2.0 的主要开发者，增加多用户支持、多线程删除、自定义路径等

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=blackboxo/CleanMyWechat&type=Date)](https://star-history.com/#blackboxo/CleanMyWechat&Date)

## 本次功能说明

本版本是在原项目基础上做的最小功能增强

### Python 版本兼容

`requirements.txt` 已改成兼容不同 Python 版本的写法，不再固定旧版 `pyinstaller==6.8.0`。运行和打包方式仍按原项目说明使用。

## 打包 EXE 方式

```Shell
pip install -r requirements.txt
pyinstaller -F -i images/icon.ico -w main.py
cp -r images dist/
./dist/main.exe
```

### 新增功能对应位置

| 功能 | 主要位置 | 说明 |
| --- | --- | --- |
| 清理前扫描预览 | `main.py` | 点击开始后先统计待清理文件，再弹窗确认 |
| 文件大小统计 | `main.py` | 统计预计释放空间，并按类型汇总 |
| 真正多线程清理 | `main.py`、`utils/multiDeleteThread.py` | 使用 `thread.start()`，并保存线程对象 |
| 新版微信目录适配 | `main.py`、`utils/selectVersion.py` | 增加 `MsgAttach`、`xwechat_files`、radium/web、日志、小程序缓存等目录 |
| 程序文件保护 | `main.py`、`utils/deleteThread.py`、`utils/multiDeleteThread.py` | 自动跳过 `.dll`、`.exe`、`.pyd`、`.pak`、数据库文件等，不把运行组件送进回收站 |
| 白名单 | `main.py`、`whitelist.txt` | 支持路径和扩展名白名单，默认保护常见办公文档 |
| 按文件类型控制 | `main.py`、`config.json` | 支持图片、视频、文档、压缩包、缓存、其他类型分别开关 |
| 自动清理和开机启动 | `main.py`、`clean_state.json` | 默认关闭，需要在 `config.json` 中手动开启 |
| 异常日志 | `main.py`、`utils/deleteThread.py`、`utils/multiDeleteThread.py` | 文件被占用或权限不足时写入 `cleanmywechat.log` |
| 配置路径统一 | `main.py`、`utils/selectVersion.py` | 统一使用项目根目录下的 `config.json` |
| Python 3.14 兼容依赖 | `requirements.txt` | 根据 Python 版本选择 PyInstaller 版本范围 |

### 1. 清理前预览

点击开始后，会先扫描文件，再弹出确认窗口。窗口会显示：

- 待清理文件数量
- 待清理空文件夹数量
- 预计释放空间
- 图片、视频、普通文件、压缩包、缓存/日志等分类统计
- 风险提示

详细扫描结果会同时写入：

```text
last_scan_preview.txt
```

确认后才会把文件移动到回收站。

### 2. 多线程修复

原代码中清理线程调用的是 `thread.run()`，实际仍然会阻塞主界面。本次改为 `thread.start()`，并保存线程对象，避免线程被提前回收。

### 3. 新版微信目录适配

新增扫描以下目录：

```text
FileStorage/MsgAttach
MsgAttach
msg/attach
xwechat_files
%AppData%/Tencent/WeChat/log
%AppData%/Tencent/WeChat/radium/web/profiles/*/Cache
%AppData%/Tencent/WeChat/radium/web/profiles/*/Code Cache
%AppData%/Tencent/WeChat/radium/web/profiles/*/GPUCache
Applet/WMPF/WeChatAppEx/XPlugin 下名称明确的 Cache、Log、Temp 类目录
```

这些目录仍然会受到“保留天数”和“清理前确认”的限制。系统区清理只进入名称明确的缓存、日志、临时目录，不再扫描 `web_shell`、`multitab`、`runtime`、`bin`、`plugins` 等运行组件目录。

### 4. 白名单

新增 `whitelist.txt`。一行写一个路径或扩展名即可，例如：

```text
D:/重要资料
.pdf
.docx
.xlsx
```

也可以在 `config.json` 的用户配置中修改：

```json
"use_whitelist": true,
"whitelist_paths": [],
"whitelist_exts": [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf"]
```

默认会跳过常见办公文档，同时强制跳过 `.dll`、`.exe`、`.pyd`、`.pak`、数据库文件等程序组件，避免误删微信或运行库文件。

### 5. 按文件类型清理

可以在 `config.json` 中调整：

```json
"clean_ext_groups": {
  "image": true,
  "video": true,
  "document": false,
  "archive": true,
  "cache": true,
  "other": true
}
```

含义如下：

- `image`：jpg、png、gif、webp、dat 等
- `video`：mp4、mov、avi、mkv 等
- `document`：docx、pdf、xlsx、pptx、txt 等
- `archive`：zip、rar、7z 等
- `cache`：tmp、cache、log 等
- `other`：其他扩展名

### 6. 自动清理和开机启动

默认关闭，避免第一次运行时误清理。需要时在 `config.json` 中修改：

```json
"global": {
  "auto_clean_enable": true,
  "auto_clean_interval_days": 30,
  "auto_clean_confirm": true,
  "run_at_startup": true,
  "startup_clean_cache_only": true
}
```

说明：

- `auto_clean_enable`：是否启用自动清理周期检查
- `auto_clean_interval_days`：间隔多少天自动扫描一次
- `auto_clean_confirm`：自动清理前是否弹窗确认
- `run_at_startup`：是否写入 Windows 当前用户开机启动项
- `startup_clean_cache_only`：开机自动清理时是否只处理缓存，默认开启，更安全

自动清理的最近执行日期会记录在：

```text
clean_state.json
```


### 安全说明

如果 Windows 弹出“无法移到回收站，是否永久删除”的提示，请选择“否”。本版已经增加保护规则，扫描和删除阶段都会跳过 `.dll`、`.exe`、`.pyd`、`.pak`、`.db` 等文件。新版微信系统区只清理明确的缓存、日志和临时目录，不清理运行组件目录。

### 7. 日志

清理或扫描中遇到文件被占用、权限不足等问题，会写入：

```text
cleanmywechat.log
```

单个文件失败不会中断整个清理流程。
