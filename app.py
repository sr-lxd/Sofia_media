"""Sofia Media: a loopback-first Flask MP3/MP4 player."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from filelock import FileLock
from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash

BASE_DIR = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=8))
LOG = logging.getLogger(__name__)


def resolve_path(value, base=BASE_DIR):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def create_app(overrides=None):
    load_dotenv(BASE_DIR / ".env", override=False)
    app = Flask(__name__)
    app.config.update(
        DATA_DIR=resolve_path(os.getenv("DATA_DIR", "data")),
        USER_DIC_FILE=resolve_path(os.getenv("USER_DIC_FILE", "user.dic")),
        DIRECTORY_MAP_FILE=BASE_DIR / "DIRECTORY_MAP.json",
        FRONTEND_CONFIG_FILE=BASE_DIR / "frontend_config.json",
        DEMO_MODE=os.getenv("DEMO_MODE", "0") == "1",
        MEDIA_ROOT=resolve_path(os.getenv("MEDIA_ROOT", "media_files")),
        ADMIN_USERNAME=os.getenv("ADMIN_USERNAME", "").strip().lower(),
        ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD", ""),
        ADMIN_PASSWORD_HASH=os.getenv("ADMIN_PASSWORD_HASH", ""),
        PUBLIC_CATEGORIES=os.getenv("PUBLIC_CATEGORIES", "public,features"),
        SOFIA_HOME_URL=os.getenv("SOFIA_HOME_URL", ""),
        CACHE_SECONDS=60,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=64 * 1024,
        TEMPLATES_AUTO_RELOAD=True,
    )
    if overrides:
        app.config.update(overrides)
    data_dir = Path(app.config["DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True)
    if not app.config.get("SECRET_KEY"):
        key = os.getenv("FLASK_SECRET_KEY", "")
        if not key:
            keyfile = data_dir / "session.key"
            with FileLock(str(keyfile) + ".lock"):
                if not keyfile.exists():
                    keyfile.write_text(secrets.token_urlsafe(48), encoding="ascii")
                key = keyfile.read_text(encoding="ascii").strip()
        app.secret_key = key

    cache = {}
    cache_lock = threading.Lock()

    def read_json(path):
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            LOG.warning("Unable to read configuration: %s", Path(path).name)
            return {}

    def categories():
        labels = read_json(app.config["FRONTEND_CONFIG_FILE"]).get("categories", {})
        directories = read_json(app.config["DIRECTORY_MAP_FILE"])
        return {key: label for key, label in labels.items() if key in directories}

    def users():
        result = {}
        path = Path(app.config["USER_DIC_FILE"])
        if not path.exists():
            return result
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fields = [part.strip() for part in line.split(":", 2)]
            if len(fields) == 3:
                result[fields[0].lower()] = {
                    "password": fields[1],
                    "categories": [cat.strip().lower() for cat in fields[2].split(",") if cat.strip()],
                }
        return result

    def password_matches(stored, supplied):
        if not stored or not supplied:
            return False
        if stored.startswith(("scrypt$", "pbkdf2$")):
            return check_password_hash(stored, supplied)
        return hmac.compare_digest(stored.encode(), supplied.encode())

    def allowed_categories():
        configured = categories()
        if session.get("public_session"):
            allowed = app.config["PUBLIC_CATEGORIES"].split(",")
        else:
            user = users().get(session.get("username", ""), {})
            allowed = user.get("categories", [])
        return [cat.strip().lower() for cat in allowed if cat.strip().lower() in configured]

    def read_history():
        try:
            value = json.loads((data_dir / "history.json").read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, ValueError):
            return []

    def append_log(event):
        with FileLock(str(data_dir / "history.lock"), timeout=10):
            history = read_history()
            cutoff = (datetime.now(TZ) - timedelta(days=1)).isoformat(timespec="seconds")
            history = [row for row in history if row.get("timestamp", "") >= cutoff]
            history.insert(0, {
                "username": session.get("username", "anonymous"),
                "event": event,
                "timestamp": datetime.now(TZ).isoformat(timespec="seconds"),
                "ip": request.remote_addr,
                "user_agent": request.headers.get("User-Agent", "")[:300],
            })
            temp = data_dir / "history.tmp"
            temp.write_text(json.dumps(history[:500], ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(data_dir / "history.json")

    def login_required(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if not session.get("logged_in"):
                if request.path in ("/api/list_mp3", "/mp3"):
                    return jsonify(error="请先登录"), 401
                return redirect(url_for("login"))
            return function(*args, **kwargs)
        return wrapped

    def list_media(category, force=False):
        directory = read_json(app.config["DIRECTORY_MAP_FILE"]).get(category)
        if not isinstance(directory, str) or not directory or ".." in directory.split("/"):
            raise ValueError("Invalid media directory")
        cache_key = (category, directory)
        with cache_lock:
            cached = cache.get(cache_key)
            if not force and cached and time.monotonic() - cached[0] < app.config["CACHE_SECONDS"]:
                return cached[1], cached[2]
        root = Path(app.config["MEDIA_ROOT"]).resolve()
        folder = (root / directory).resolve()
        if not folder.is_relative_to(root):
            raise ValueError("Media directory escapes root")
        files = [p.name for p in folder.iterdir() if p.is_file() and p.resolve().is_relative_to(root)] if folder.is_dir() else []
        mapping, playlist = {}, []
        for name in sorted(set(files), key=str.casefold):
            ext = Path(name).suffix.lower()
            if ext not in (".mp3", ".mp4") or any(c in name for c in "\r\n/\\"):
                continue
            key = hashlib.sha256((category + "/" + name).encode()).hexdigest()[:20] + ext
            mapping[key] = {"folder": folder, "name": name}
            playlist.append({"display": name, "play": key})
        with cache_lock:
            cache[cache_key] = (time.monotonic(), mapping, playlist)
        return mapping, playlist

    @app.before_request
    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        if request.method == "POST":
            token = request.form.get("csrf_token", "")
            if not hmac.compare_digest(token.encode(), session["csrf_token"].encode()):
                return "页面已过期，请刷新后重试。", 400

    @app.context_processor
    def template_settings():
        return {"csrf_token": session.get("csrf_token", ""), "sofia_home_url": app.config["SOFIA_HOME_URL"]}

    @app.route("/healthz")
    def health():
        return jsonify(status="ok", service="sofia-media")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        public = [key.strip() for key in app.config["PUBLIC_CATEGORIES"].split(",") if key.strip() in categories()]
        if request.method == "POST":
            action = request.form.get("action", "登录")
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            if action == "公共账号登录" and public:
                session.clear()
                session.update(logged_in=True, public_session=True, username="guest", last_category=public[0])
                append_log("公共账号登录")
                return redirect(url_for("index"))
            if action == "管理员登录":
                admin_password = app.config["ADMIN_PASSWORD_HASH"] or app.config["ADMIN_PASSWORD"]
                if username == app.config["ADMIN_USERNAME"] and password_matches(admin_password, password):
                    session.clear()
                    session.update(admin_logged_in=True, username=username)
                    append_log("管理员登录")
                    return redirect(url_for("history"))
                error = "管理员用户名或密码错误。"
            else:
                user = users().get(username)
                allowed = [cat for cat in user.get("categories", []) if cat in categories()] if user else []
                if user and allowed and password_matches(user["password"], password):
                    session.clear()
                    session.update(logged_in=True, username=username, last_category=allowed[0])
                    append_log("用户登录")
                    return redirect(url_for("index"))
                error = "用户名、密码或目录权限不正确。"
        return render_template("login.html", error=error, public_enabled=bool(public), demo_mode=app.config["DEMO_MODE"])

    @app.route("/history")
    def history():
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return render_template("history.html", logs=read_history())

    @app.route("/logout")
    def logout():
        if session.get("username"):
            append_log("登出")
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def index():
        allowed = allowed_categories()
        if not allowed:
            session.clear()
            return redirect(url_for("login"))
        return render_template("index.html", categories=categories(), allowed_categories=allowed, username=session.get("username", ""))

    @app.route("/api/list_mp3")
    @login_required
    def list_mp3():
        category = (request.args.get("category") or session.get("last_category", "")).strip().lower()
        if category not in allowed_categories():
            return jsonify(error="无权访问这个目录"), 403
        try:
            _, playlist = list_media(category, request.args.get("force", "").lower() in ("1", "true", "yes"))
        except (OSError, ValueError):
            LOG.warning("Unable to list media for category %s", category)
            return jsonify(error="无法读取媒体目录，请检查媒体文件与目录配置。"), 503
        session["last_category"] = category
        append_log("列表:" + category)
        return jsonify(playlist)

    @app.route("/mp3", methods=["GET", "HEAD"])
    @login_required
    def media():
        category = (request.args.get("category") or session.get("last_category", "")).strip().lower()
        if category not in allowed_categories():
            return jsonify(error="无权访问这个目录"), 403
        key = request.args.get("playname", "")
        if not key:
            return jsonify(error="缺少曲目名称"), 400
        try:
            mapping, _ = list_media(category)
            entry = mapping.get(key)
            if not entry:
                return jsonify(error="曲目不存在，请刷新列表。"), 404
            mime = "video/mp4" if entry["name"].lower().endswith(".mp4") else "audio/mpeg"
            path = (entry["folder"] / entry["name"]).resolve()
            if not path.is_file() or not path.is_relative_to(Path(app.config["MEDIA_ROOT"]).resolve()):
                return jsonify(error="曲目不存在，请刷新列表。"), 404
            response = send_file(path, mimetype=mime, conditional=True)
            response.headers["Cache-Control"] = "private, no-cache"
            if request.method == "GET":
                append_log("播放:" + entry["name"])
            return response
        except (OSError, ValueError):
            LOG.warning("Unable to stream media for category %s", category)
            return jsonify(error="媒体暂时无法读取，请刷新或检查配置。"), 503

    @app.route("/help.html")
    def help_page():
        return render_template("help.html")

    return app


app = create_app()

if __name__ == "__main__":
    from run import main
    main(app)
