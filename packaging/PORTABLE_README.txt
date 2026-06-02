EM Workbench / 电磁学工作台
Windows 便携预览版

使用方法

1. 解压整个文件夹，不要只单独拖出 exe。
2. 双击 EMWorkbench.exe。
3. 第一次打开如果 Windows SmartScreen 提醒“未知发布者”，这是因为当前预览版尚未做代码签名。
   请选择“更多信息” -> “仍要运行”。

这个版本不需要安装 Python，不需要启动服务器，也不需要浏览器网址。

分享给朋友时，请直接发送整个 zip 文件：

EMWorkbench-0.1.0-windows-x64-portable.zip

注意事项

- 请保持 EMWorkbench.exe 和 _internal 文件夹在同一目录。
- 这是静电场模块预览版，重点用于体验 2D/3D 工作台、预设、电场计算和探针。
- 如果界面无法打开，请确认系统是 Windows 10/11 64 位，并先解压后运行。
- 便携包默认使用 CPU JIT，不要求安装 CUDA。源码运行版本可以按项目 README 启用可选 NVIDIA CUDA 加速。

