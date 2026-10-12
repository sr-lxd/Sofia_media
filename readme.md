# Sofia Media

基于 Flask 的 MP3 / MP4 媒体播放器，从本机 `media_files` 目录读取媒体文件。
默认通过 Waitress 运行在 **http://127.0.0.1:15001**，仅供本机访问。

## 功能

- 普通账号登录、公共目录入口、管理员历史页和使用帮助。
- 按账号控制目录：每个账号只能看到并播放被授权的目录，越权请求会被拒绝。
- 播放器下方显示“目录：当前曲目”，目录面板可收起。
- 长曲名省略显示，点击展开完整标题，再次点击收起。
- 搜索、排序、顺序 / 随机播放、MP3 音频与 MP4 视频切换。
- 浏览器保存上次目录、曲目和播放位置。自动播放受限时，点击播放继续。
- 支持拖动播放进度，HTTP Range 只读取需要的片段。
- Windows / Linux / macOS 使用同一套程序；访问记录采用跨平台文件锁。

## 账号与目录权限

权限由 `user.dic` 控制，每行一个账号：

```text
用户名:密码或Werkzeug密码哈希:目录标识1,目录标识2
```

- 目录标识到文件夹的映射见 `DIRECTORY_MAP.json`；界面显示名见 `frontend_config.json`。
- 登录后只会出现该账号被授权的目录；列表和播放接口都会再次校验权限，越权返回 403。
- 修改 `user.dic` 后刷新页面即可生效，无需重启程序。
- 公共目录入口只开放 `PUBLIC_CATEGORIES` 列出的目录，适合开放给访客或公共设备。
- 管理员账号只用于查看播放历史，不进入播放器。

## 使用场合举例

### 中小学教育场景

同一套程序，给不同账号分配不同目录，就能覆盖多种角色。目录标识取自 `DIRECTORY_MAP.json`。

| 使用对象 | user.dic 配置示例 | 效果 |
|---|---|---|
| 语文教研组 | `yuwen:密码:catalog,reading,famous,wholebook,quintessence` | 只出现 论坛、读书、名著、整书、古文；音乐、视频、时政等目录不出现 |
| 学生阅读课 / 图书馆终端 | `reader:密码:reading,storytelling,wholebook` | 只有 读书、评书、整书 三个目录，天然屏蔽其余内容 |
| 初中年级组 | `junior:密码:children,junior` | 只有 儿童、初中 两个目录，适合听力、朗读素材 |
| 高中年级组 | `senior:密码:senior,career,education` | 只有 高中、生涯、教育，面向升学与生涯规划 |
| 科技 / AI 社团 | `stem:密码:science,ai` | 只有 科技、AI 两个目录 |
| 校园电视台 / 活动大屏 | `studio:密码:features,videosongs,film` | 只有 特色、影音、电影，用于活动播放 |
| 访客 / 开放日设备 | `PUBLIC_CATEGORIES=public,features` | 无需登录，只有 音乐、特色 两个目录 |

要点：权限写在账号行里，改一个账号不影响其他人；学生用机只挂阅读目录，就不会误播其他内容；管理员用独立管理员账号，只查看播放历史，不参与播放。

### 其他场景

- 家庭：孩子账号 `kid:密码:children,reading,storytelling`，家长账号使用全部目录。
- 会议室 / 活动室：`meeting:密码:selected,features`，只放精选与特色视频。
- 个人多设备：按兴趣拆分，如 `music:密码:public,old`（音乐与旧闻）、`health:密码:regimen`（养生）。

## 快速开始

需要 Python 3.10 或更新版本。FFmpeg 仅用于生成演示媒体，日常播放不依赖它。

### Windows

```powershell
git clone https://github.com/sr-lxd/Sofia_media.git
cd Sofia_media
.\setup.bat
.\start.bat
```

打开 <http://127.0.0.1:15001>。首次安装从示例复制 `.env` 和 `user.dic`，已有配置不会被覆盖。
若端口被占用，使用 `start.bat --port 15002`，然后访问对应端口。

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python tools/bootstrap.py
python run.py
```

也可以运行 `python app.py`。正式启动入口使用 Waitress，不开启 Flask 调试模式。

## 虚拟演示配置

仓库中的账号与密码均为虚拟示例。

| 入口 | 用户名 | 密码 | 可见目录 |
|---|---|---|---|
| 普通登录 | `demo` | `demo-pass` | 音乐、特色 |
| 普通登录 | `reader` | `reader-pass` | 音乐、精选、读书 |
| 管理员登录 | `demo-admin` | `demo-admin-pass` | 仅播放历史 |
| 公共目录 | 无需输入 | 无需输入 | `PUBLIC_CATEGORIES` 指定的目录 |

替换为个人配置时，编辑被 Git 忽略的 `.env` 和 `user.dic`，并将 `DEMO_MODE=0`，隐藏登录页上的演示提示。
管理员密码也可通过 `ADMIN_PASSWORD_HASH` 设置为 Werkzeug 生成的 `scrypt` / `pbkdf2` 哈希，优先于 `ADMIN_PASSWORD`。

`user.dic` 每行格式：

```text
用户名:密码或Werkzeug密码哈希:目录标识1,目录标识2
```

修改用户及目录权限后会在后续请求生效，无需重启。

## 媒体目录

媒体根目录为 `media_files`，可用 `MEDIA_ROOT` 改为其他路径。

```text
media_files/
├── mp3_public/     # 音乐
├── mp3_selected/   # 精选
├── mp3_reading/    # 读书
└── mp4_public/     # 特色视频
```

将自己的 `.mp3` / `.mp4` 文件放入对应目录，再点击播放器“刷新”。
每个目录只读取当前层的媒体文件，不递归扫描。空目录会显示空列表。

安装了 FFmpeg 时，可生成无版权素材的测试音和纯色视频：

```powershell
.\.venv\Scripts\python.exe tools\make_demo.py
```

生成的媒体保存在 `media_files`，不会上传到 Git。没有 FFmpeg 时，直接加入自己的媒体即可。

## 配置文件

| 文件 / 设置 | 用途 |
|---|---|
| `.env.example` | 可公开的虚拟配置模板 |
| `.env` | 本机私有设置，不入 Git |
| `user.dic.example` | 虚拟用户与权限示例 |
| `user.dic` | 本机用户文件，不入 Git |
| `DIRECTORY_MAP.json` | 目录标识与媒体子目录的映射 |
| `frontend_config.json` | 目录标识与界面名称的映射 |
| `APP_PORT` | 默认端口，可被 `--port` 覆盖 |
| `MEDIA_ROOT` | 媒体根目录，可设置绝对路径 |
| `PUBLIC_CATEGORIES` | 公共入口可访问的目录；留空关闭公共入口 |
| `SOFIA_HOME_URL` | 可选的首页链接，默认不显示 |
| `DATA_DIR` | 会话密钥与历史文件目录，默认 `data` |

相对路径以项目目录为基准。环境变量优先于 `.env`。
不设置 `FLASK_SECRET_KEY` 时，首次运行生成随机密钥并保存在 `data/session.key`。
修改 `.env` 后重启程序。媒体列表缓存 60 秒，“刷新”会绕过该目录缓存。

## 页面与接口

| 路径 | 用途 |
|---|---|
| `/login` | 普通、管理员与公共目录登录 |
| `/` | 播放器 |
| `/history` | 管理员查看最近 24 小时记录，最多 500 条 |
| `/help.html` | 操作帮助 |
| `/api/list_mp3?category=public` | 已登录用户获取有权限的媒体列表 |
| `/mp3?category=public&playname=<key>` | 已登录用户播放媒体，支持 GET / HEAD |
| `/healthz` | 无需登录的服务健康检查 |

会话保存于浏览器签名 Cookie，登录表单包含 CSRF 令牌。
MP4 能否播放取决于浏览器的编码支持，演示视频采用 H.264 / AAC。

## 检查与测试

```powershell
.\start.bat --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖登录与权限、目录可见性、媒体列表过滤、HEAD 与 Range、文件边界检查、失败响应及历史记录。

启动失败时先检查依赖和端口。退出前台服务使用 `Ctrl+C`。
程序没有自动创建计划任务，也不会自动暴露到局域网。

## 公开仓库内容

公开文件包括程序、页面、样式、虚拟配置示例和测试。
真实配置、账号文件、会话密钥、历史记录、日志、媒体文件、虚拟环境及旧版备份均被 `.gitignore` 排除。

相关运行机制可参阅 [Waitress 配置文档](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html)、[Flask 文件响应文档](https://flask.palletsprojects.com/en/stable/api/#flask.send_file)和 [filelock 文档](https://py-filelock.readthedocs.io/en/latest/)。
