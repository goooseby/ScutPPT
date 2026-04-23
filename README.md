# GetPPTApp

GetPPTApp 是一个用于下载华南理工大学教学平台课件/PPT 的桌面工具。项目本质上是在爬虫逻辑外加了一层 PySide6 图形界面，方便登录、扫描课程、选择课程并批量下载 PPT 图片，最后合并为 PDF。

## 功能

- 内置浏览器登录 SCUT 教学平台
- 自动提取登录 Cookie、用户 ID、租户 ID 和 Token
- 按日期范围扫描课程表
- 按课程分组展示扫描结果
- 支持筛选、全选、反选和勾选下载
- 下载 PPT 图片并合并为 PDF
- 支持暂停、继续和取消下载
- 支持设置下载目录、超时时间、重试次数、请求间隔和并发数

## 环境要求

推荐使用 Python 3.11 或 3.12。

安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

主要依赖：

- `PySide6`：桌面界面和内置浏览器
- `requests`：请求接口和下载图片
- `Pillow`：图片处理和 PDF 合并

## 运行

```powershell
python main.py
```

首次启动时会提示选择下载保存目录，也可以在“设置”里修改。

## 使用流程

1. 启动程序。
2. 点击“登录并导入”，在内置浏览器中完成学校平台登录。
3. 登录成功后点击“导入登录态”。
4. 回到主界面，设置开始日期和结束日期。
5. 点击“扫描课表”。
6. 在课程列表中勾选要下载的课程。
7. 点击“下载选中”。

下载完成后，每节课会保存到配置的下载目录中，并生成对应 PDF。

## 配置文件

主配置文件是项目根目录下的 `config.json`。

示例：

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

字段说明：

- `download_dir`：下载保存目录
- `max_workers`：图片下载并发数
- `timeout`：网络请求超时时间，单位秒
- `retries`：单张图片下载失败后的重试次数
- `sleep_ms`：下载任务提交间隔，单位毫秒
- `keep_images`：是否保留下载后的原始图片

## 项目结构

```text
GetPPTApp/
├── main.py                  # 程序入口和主界面
├── config.json              # 用户配置
├── requirements.txt         # Python 依赖
├── auth/
│   └── browser_login.py     # 内置浏览器登录和登录态提取
├── core/
│   ├── config.py            # 配置读写
│   └── downloader.py        # 课程扫描、图片下载、PDF 合并
└── ui/
    ├── settings_dialog.py   # 设置窗口
    ├── style.qss            # Qt 样式
    └── theme.py             # 样式加载
```

## 注意事项

- 本项目仅用于个人学习和课程资料整理。
- 请合理设置并发数和请求间隔，避免对学校平台造成过高访问压力。
- 登录态来自内置浏览器 Cookie，失效后需要重新登录。
- 如果安装 `PySide6` 后无法打开登录窗口，请确认当前 Python 环境和系统架构一致。

