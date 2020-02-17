# AutoDeleteFileOnPCWechat

[![](https://img.shields.io/badge/platform-win64-lightgrey)](https://github.com/blackboxo/AutoDeleteFileOnPCWechat/releases) [![](https://img.shields.io/github/v/release/blackboxo/AutoDeleteFileOnPCWechat)](https://github.com/blackboxo/AutoDeleteFileOnPCWechat/releases) [![](https://img.shields.io/github/downloads/blackboxo/AutoDeleteFileOnPCWechat/total)](https://github.com/blackboxo/AutoDeleteFileOnPCWechat/releases)

自动删除 PC 端微信自动下载的大量文件、视频、图片等数据内容，解放你的空间。

该工具不会删除文字的聊天记录，请放心使用。

程序启动较慢，删除过程中如出现转圈等现象请耐心等待，删除结束将会有提示。

**如何找到微信文件的存储路径：**

点击 PC 端微信左下角的按钮 -> 设置 -> 通用设置 -> 打开文件夹 -> 复制文件资源管理器的完整路径


[国内地址 - 点击下载](
https://deletefileonpcwechat.oss-cn-shanghai.aliyuncs.com/%E5%BE%AE%E4%BF%A1%E6%95%B0%E6%8D%AE%E8%87%AA%E5%8A%A8%E5%88%A0%E9%99%A4%E5%B7%A5%E5%85%B7.exe)

[Github Release - 点击下载](
https://github.com/blackboxo/AutoDeleteFileOnPCWechat/releases)

**报病毒了怎么办？**

属于 Windows Defender 的误报，我正在解决。软件本身没有问题，已开源，如有 Python 3 环境也可自己直接执行。

暂时的解决办法：

打开设置，搜索“病毒和威胁防护”->“病毒和威胁防护”设置->管理设置->关闭“实时保护”->重新下载软件打开->使用完成后自行打开实时保护。

![](https://markdown-pic-blackboxo.oss-cn-shanghai.aliyuncs.com/20200217205308.png)

## 特性
1. 自由设置想要删除的文件类型，包括图片类缓存、文件、图片、视频；
2. 自由设置需要删除的文件的距离时间，默认 24 个月；
3. 删除后的文件放置在回收站中，检查后自行清空，防止删错需要的文件；

## 运行截图

![](https://markdown-pic-blackboxo.oss-cn-shanghai.aliyuncs.com/20200216161434.png)

## 微信现状

下载两年时间，微信一个软件就占用多达 33.5 G 存储空间。其中大部分都是与自己无关的各大群聊中的文件、视频、图片等内容，且很久以前的文件仍旧存在电脑中。

![](https://markdown-pic-blackboxo.oss-cn-shanghai.aliyuncs.com/20200213142805.png)

## 待改进

- [ ] 运行占用较多磁盘，待优化
- [ ] 增加直接删除文件和文件夹选项，不放入回收站
- [ ] 增加中途暂停及停止
- [ ] 支持 Mac 平台