# Clean My Wechat

Clean My Wechat 是一个 Windows 桌面工具，用来扫描并清理 PC 微信产生的缓存、日志、图片、视频和旧文件，释放本地磁盘空间。

工具不会清理文字聊天记录。默认会先扫描并展示清理预览，用户确认后才执行清理。

## 界面预览

首页：

![Clean My Wechat 首页](images/README-home.png)

清理设置：

![Clean My Wechat 设置](images/README-settings.png)

## 主要功能

- 自动识别常见微信账号目录，也支持手动选择 `WeChat Files` 或新版 `xwechat_files` 路径。
- 支持多个微信账号分别配置清理范围和保留时间。
- 支持清理图片缓存、小程序和公众号缓存、图片、视频、收到的文档。
- 视频目录按视频整体处理，目录内缩略图和附属文件会跟随视频选项清理。
- 支持按月份目录加速扫描旧视频目录，减少大量文件遍历带来的卡顿。
- 清理前显示确认窗口，按表格列出类型、大小和路径。
- 默认移动到回收站，也可在设置中开启“直接删除，不移动到回收站”。
- 支持开机自启动和定期自动清理，默认关闭。

## 使用方式

1. 打开应用后点击“设置”。
2. 选择需要清理的微信账号，并勾选“启用这个账号的清理”。
3. 勾选需要清理的范围，例如“视频”或“图片缓存、小程序和公众号缓存”。
4. 设置保留时间，例如 `700` 表示 700 天以内不清理。
5. 保存设置后返回首页，点击“扫描并清理”。
6. 在确认窗口检查待清理列表，确认后开始清理。

## 清理范围说明

| 选项 | 说明 |
| --- | --- |
| 图片缓存、小程序和公众号缓存 | 清理缓存、日志、小程序缓存和公众号相关缓存 |
| 图片 | 清理微信图片目录中的旧图片 |
| 视频 | 清理微信视频目录中的旧视频及缩略图等附属文件 |
| 收到的文档 | 清理收到的普通文件、文档、压缩包和其他附件 |

混合附件目录会按文件扩展名逐个筛选，不会整月删除，避免把未勾选类型一起清理。

## 安全说明

- 清理前会先扫描并弹出确认窗口。
- 默认清理方式是移动到回收站。
- 开启“直接删除，不移动到回收站”后，完成提示会显示“文件已直接删除”。
- 程序会跳过 `.dll`、`.exe`、`.db`、`.pyd`、`.pak` 等运行组件和数据库文件。
- 白名单文件写在 `whitelist.txt`，一行一个路径或扩展名。

## 开发与运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

本项目也可以使用 `uv` 运行：

```powershell
$env:UV_CACHE_DIR='.uv-cache'
uv run python main.py
```

## 打包

```powershell
$env:UV_CACHE_DIR='.uv-cache'
uv run pyinstaller -F -i images/icon.ico -w main.py
Copy-Item -Recurse -Force images dist/images
Compress-Archive -Force dist/main.exe, dist/images dist/CleanMyWechat.zip
```

打包产物位于：

```text
dist/main.exe
dist/CleanMyWechat.zip
```

## 项目结构

```text
main.py              应用入口和主要 UI 逻辑
utils/               删除线程、路径识别和扫描辅助逻辑
images/              UI 文件、图标和 README 截图
config.json          本地运行配置
whitelist.txt        清理白名单
last_scan_preview.txt 最近一次扫描预览
```

## 致谢

感谢原项目贡献者和社区 PR 对多账号、路径识别、企业微信兼容、清理预览和新版微信目录适配的改进。
