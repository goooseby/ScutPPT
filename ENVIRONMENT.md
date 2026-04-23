# GetPPTApp 环境配置说明

## 1. 运行环境

- Python 3.13.x
  - 当前检测到的可用解释器：`C:/Users/20688/AppData/Local/Programs/Python/Python313/python.exe`
  - 推荐使用虚拟环境来隔离依赖。

## 2. 依赖库

该项目核心依赖如下：

- `PySide6`
  - 用于构建桌面 GUI 界面。
  - 需要支持 `QtWebEngine`，因为项目使用 `PySide6.QtWebEngineWidgets.QWebEngineView` 来完成浏览器登录。
- `requests`
  - 用于发送 HTTP 请求，访问课程 API 和下载 PPT 图片。
- `Pillow`
  - 用于打开、转换和合并下载的图片为 PDF。

## 3. 安装步骤

在项目根目录下执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install PySide6 requests pillow
```

如果你使用 CMD：

```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install PySide6 requests pillow
```

## 4. 运行项目

激活虚拟环境后，直接运行：

```powershell
python main.py
```

## 5. 项目配置文件

- `config.json`
  - 这是主程序会读取/写入的配置文件。
  - 存储默认保存目录、并发数、超时、重试次数、请求间隔、是否保留原图等。

默认内容示例：

```json
{
  "download_dir": "C:/Users/GetPPToutput",
  "max_workers": 8,
  "timeout": 60,
  "retries": 3,
  "sleep_ms": 200,
  "keep_images": true
}
```

## 6. 关键模块说明

- `main.py`
  - 程序入口，负责 UI 布局、用户交互、扫描与下载任务调度。
- `auth/browser_login.py`
  - 内置浏览器登录窗口；登录后采集 `scut.edu.cn` 域名下的 Cookie、`user_id`、`tenant_id`、JWT Token。
- `core/config.py`
  - 配置读取与保存。
- `core/downloader.py`
  - 课程扫描、PPT 图片下载、图片合并为 PDF、暂停/取消逻辑等核心功能。
- `ui/settings_dialog.py`
  - 设置面板，允许用户调整保存目录、并发、超时、重试、请求间隔、是否保留原图。

## 7. 额外说明

- 当前代码中没有检测到 `requirements.txt` 或 `pyproject.toml`。
- 建议首次进入项目的开发者先搭建虚拟环境，并安装上述依赖。
- 如果你在安装 `PySide6` 后遇到 `QtWebEngine` 相关问题，请确认使用的是官方 `PySide6` 包，并且 Python 与系统架构一致。
