# LifeButler Windows 便携包打包说明

本文档用于在 Windows 电脑上生成 LifeButler 用户测试版便携包。当前 macOS 环境不直接产出 Windows exe；Windows 可执行文件应在 Windows 环境构建。

## 产物

脚本会生成：

```text
dist\LifeButler-Windows\LifeButler.exe
dist\LifeButler-Windows.zip
```

这是便携包，不是 MSI 安装器。同学解压后双击 `LifeButler.exe` 即可运行。

## 前置条件

- Windows 10 或 Windows 11
- Python 3.10 或更高版本
- 已确认图标，并已导出：
  - `resources\icon\LifeButler-icon.png`
  - `resources\icon\LifeButler.ico`

如果只有 PNG，脚本会自动转换出 `.ico`。

## 打包命令

在项目根目录打开 PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\build_windows.ps1
```

脚本会自动：

1. 创建 `.venv`
2. 安装 `requirements.txt`
3. 安装 `pyinstaller` 和 `pillow`
4. 生成 `LifeButler.exe`
5. 压缩为 `dist\LifeButler-Windows.zip`

## 验证

打包完成后：

1. 打开 `dist\LifeButler-Windows\LifeButler.exe`
2. 确认主窗口能启动。
3. 在设置页确认数据库路径可读。
4. 试用快速收集、任务池、记账、目标管理。

## 注意事项

- 不要把 `.venv` 放进最终发给用户的压缩包。
- 不要把本机 `data\lifebutler.db` 发给同学。
- Windows 首次运行会在同学电脑上创建自己的本地数据库。
- 如果 Windows Defender 拦截未签名 exe，这是未签名测试包的正常限制；本项目当前不做代码签名。
