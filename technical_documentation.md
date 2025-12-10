# CleanMyWechat 技术文档

## 1. 清理目标分类

CleanMyWechat 按照不同的文件类型和用途，将清理目标分为以下4个类别：

| 分类 | 描述 | 配置项 |
|------|------|--------|
| 图片缓存 | 微信聊天产生的图片缓存文件 | `clean_pic_cache` |
| 文件 | 微信聊天中接收的文件 | `clean_file` |
| 图片 | 微信聊天中接收的图片 | `clean_pic` |
| 视频 | 微信聊天中接收的视频 | `clean_video` |

## 2. 清理目录

每个分类对应多个硬编码的清理目录，程序会根据配置项决定是否清理这些目录：

### 2.1 图片缓存清理目录

- `Attachment`
- `FileStorage/Cache`
- `cache`
- `new/cache/path`

### 2.2 文件清理目录

- `Files`
- `FileStorage/File`
- `msg/file`
- `FileStorage/MsgAttach`
- `FileStorage/Sns/cache`

### 2.3 图片清理目录

- `Image/Image`
- `FileStorage/Image`
- `msg/attach`
- `new/image/path`

### 2.4 视频清理目录

- `Video`
- `FileStorage/Video`
- `msg/video`
- `new/video/path`

## 3. 清理条件

程序会根据以下条件决定是否清理文件或目录：

### 3.1 基本条件

1. 配置项对应分类的开关必须为开启状态
2. 文件或目录的修改时间必须早于设定的保留天数

### 3.2 文件清理条件

对于单个文件，程序会检查其修改时间：
- 如果文件的修改时间距离当前时间超过设定的保留天数，则会被清理

### 3.3 目录清理条件

对于 YYYY-MM 格式的目录，程序会检查其目录名：
- 如果目录名为 YYYY-MM 格式（如 2023-01）
- 且该目录的年月早于截止日期（当前日期减去保留天数）
- 则会被整体清理

## 4. 清理逻辑

### 4.1 目录处理规则

1. 对于每个分类的第一个目录，直接处理其中的文件
2. 对于其他目录，递归搜索所有 YYYY-MM 格式的子目录
3. 对于非 YYYY-MM 格式的子目录，直接处理其中的文件

### 4.2 YYYY-MM 目录处理逻辑

```python
# 计算截止日期
now = datetime.datetime.now()
td = now - datetime.timedelta(days=day)
td_year = td.year
td_month = td.month

# 检查目录是否早于截止日期
def __before_deadline(cyear, cmonth, td_year, td_month):
    if cyear < td_year:
        return True
    elif cyear > td_year:
        return False
    elif cyear == td_year:
        return cmonth < td_month
```

## 5. 配置说明

### 5.1 配置文件结构

```json
{
  "data_dir": ["微信用户目录1", "微信用户目录2"],
  "users": [
    {
      "wechat_id": "用户ID",
      "clean_days": "365",
      "is_clean": true,
      "clean_pic_cache": true,
      "clean_file": false,
      "clean_pic": true,
      "clean_video": true,
      "is_timer": true,
      "timer": "0h"
    }
  ]
}
```

### 5.2 配置项说明

| 配置项 | 类型 | 描述 | 默认值 |
|--------|------|------|--------|
| `wechat_id` | 字符串 | 微信用户ID | - |
| `clean_days` | 字符串 | 保留天数 | "365" |
| `is_clean` | 布尔值 | 是否清理该用户数据 | true |
| `clean_pic_cache` | 布尔值 | 是否清理图片缓存 | true |
| `clean_file` | 布尔值 | 是否清理文件 | false |
| `clean_pic` | 布尔值 | 是否清理图片 | true |
| `clean_video` | 布尔值 | 是否清理视频 | true |
| `is_timer` | 布尔值 | 是否启用定时清理 | true |
| `timer` | 字符串 | 定时清理时间 | "0h" |

## 6. 线程管理

程序使用多线程进行清理操作，每个用户使用一个独立的线程，确保清理过程不会阻塞主线程。

### 6.1 线程安全机制

- 使用 QMutex 确保共享变量的线程安全
- 使用信号-槽机制传递清理进度
- 线程完成后自动删除，防止内存泄漏

## 7. 空间占用扫描

程序提供空间占用扫描功能，用于扫描每个微信用户目录的总大小，并显示在配置窗口中。

### 7.1 扫描逻辑

1. 使用 SpaceScanThread 线程进行扫描
2. 直接计算整个用户目录的大小，包括所有子目录
3. 按占用空间从大到小排序显示

## 8. 注意事项

1. 清理操作不可逆，请谨慎配置保留天数
2. 程序将文件/目录发送到回收站，不会直接删除
3. 建议定期备份重要文件
4. 清理过程中请勿关闭程序
5. 清理完成后请及时清空回收站，释放磁盘空间

## 9. 技术栈

- Python 3.8+
- PyQt5 GUI 框架
- QThread 多线程
- JSON 配置管理
- PyInstaller 编译

## 10. 编译说明

使用 PyInstaller 编译为可执行文件：

```bash
pyinstaller --onefile --windowed --icon=images/icon.ico main.py
```

编译后的可执行文件位于 `dist` 目录下。
