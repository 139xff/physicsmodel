# EM Workbench / 电磁学工作台

[English README](README.md)

EM Workbench 是一个面向大学电磁学学习与探索的开放式工作台。当前版本聚焦 **静电场模块**：你可以自由搭建电荷源组合，在 2D / 3D 视图之间切换，观察电场可视化，并用探针读取电势和电场数值。

它不是传统“按步骤完成实验”的教学平台，而是一个更自由的电磁学建模与观察工具。

## 当前功能

- 添加和编辑多种静电源：
  - 点电荷
  - 均匀带电线段
  - 带电圆环
  - 带电圆盘
  - 无限大带电平面
  - 带电球壳
- 2D / 3D 视图切换，切换时不会重置场景。
- 2D 视图支持电场矢量和电势热力图。
- 3D 视图支持静电源几何体和三维场矢量箭头。
- 探针可以读取：
  - 电势 `V`
  - 电场向量 `E`
  - 电场大小 `|E|`
  - 各个电荷源的贡献
- 支持电偶极子等可编辑预设场景。
- 支持快速预览和精细计算两种求解模式。
- 支持 Windows 便携桌面包，方便发给朋友直接使用。

## 直接给别人使用

推荐发送这个文件：

```text
dist/EMWorkbench-0.1.0-windows-x64-portable.zip
```

朋友拿到后：

1. 解压整个 zip。
2. 打开 `EMWorkbench` 文件夹。
3. 双击 `EMWorkbench.exe`。

不需要安装 Python，不需要启动服务器，也不需要输入网址。

注意：`dist/` 目录不会提交到 Git。正式分享时，建议把 zip 上传到 GitHub Releases，而不是放进仓库源码里。

## 开发环境

本项目严格使用项目内置的 uv：

```powershell
.\.tools\uv\uv.exe sync
```

如果还没有 `.tools/uv/uv.exe`，先执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_uv.ps1
```

项目开发不要直接使用全局 `pip`、全局 `python`、npm 或 Node 包管理工具。

## 运行网页开发版

```powershell
.\.tools\uv\uv.exe run uvicorn em_workbench.app:app --reload
```

然后打开 Uvicorn 输出的本地地址。

## 从源码运行桌面版

安装桌面依赖：

```powershell
.\.tools\uv\uv.exe sync --extra desktop
```

检查桌面运行环境：

```powershell
.\.tools\uv\uv.exe run --extra desktop em-workbench-desktop --check
```

启动桌面应用：

```powershell
.\.tools\uv\uv.exe run --extra desktop em-workbench-desktop
```

## 打包 Windows 便携版

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_desktop.ps1
```

生成结果：

```text
dist/EMWorkbench/
dist/EMWorkbench-0.1.0-windows-x64-portable.zip
```

## 验证

代码检查和测试：

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider
```

打包后的桌面程序可以这样做自检：

```powershell
$p = Start-Process -FilePath .\dist\EMWorkbench\EMWorkbench.exe -ArgumentList '--check' -Wait -PassThru
$p.ExitCode
```

返回 `0` 表示桌面入口可启动。

## 项目结构

```text
web/                  前端静态页面、样式、ES modules、本地 Three.js 资源
src/em_workbench/     FastAPI 应用、桌面 bridge、场景模型、物理求解器
tests/                单元测试、API 测试、求解器测试、浏览器测试、桌面 bridge 测试
scripts/              uv 初始化、报告生成、前端资源、桌面打包脚本
packaging/            PyInstaller 配置和便携包说明
docs/                 设计规格与开发计划
reports/              每阶段任务的 HTML 工程报告
```

## 当前边界

当前版本只做静电场模块，暂不包含：

- 用户账号
- 教师后台
- 成绩排行
- 多人协作
- 静磁场
- 电磁感应
- 电磁波
- 科研级高精度导出

## 注意事项

- Three.js 和 OrbitControls 已经作为本地资源固定在仓库中，运行时不依赖 CDN。
- 数值计算以 Python 求解器为准，前端只负责交互和可视化。
- 当前 Windows 桌面包尚未做代码签名，所以第一次运行时 Windows SmartScreen 可能提示“未知发布者”。
