import json
import tempfile
import unittest
from pathlib import Path

from app import create_app


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "media" / "music").mkdir(parents=True)
        (self.root / "media" / "private").mkdir()
        (self.root / "media" / "music" / "中文曲目.mp3").write_bytes(b"0123456789")
        (self.root / "media" / "music" / "sample.mp4").write_bytes(b"video")
        (self.root / "media" / "music" / "ignored.txt").write_text("ignored")
        self.userfile = self.root / "user.dic"
        self.userfile.write_text("demo:demo-pass:public\n", encoding="utf-8")
        self.mapfile = self.root / "map.json"
        self.mapfile.write_text(json.dumps({"public": "music", "private": "private"}), encoding="utf-8")
        self.labels = self.root / "labels.json"
        self.labels.write_text(json.dumps({"categories": {"public": "音乐", "private": "私有"}}), encoding="utf-8")
        self.application = create_app({
            "TESTING": True, "SECRET_KEY": "virtual-unit-test-key",
            "DATA_DIR": self.root / "data", "MEDIA_ROOT": self.root / "media",
            "USER_DIC_FILE": self.userfile, "DIRECTORY_MAP_FILE": self.mapfile,
            "FRONTEND_CONFIG_FILE": self.labels,
            "PUBLIC_CATEGORIES": "public", "ADMIN_USERNAME": "demo-admin",
            "ADMIN_PASSWORD": "demo-admin-pass", "ADMIN_PASSWORD_HASH": "",
        })
        self.client = self.application.test_client()

    def get(self, *args, **kwargs):
        response = self.client.get(*args, **kwargs)
        self.addCleanup(response.close)
        return response

    def login(self, action="登录", username="demo", password="demo-pass"):
        self.get("/login")
        with self.client.session_transaction() as state:
            token = state["csrf_token"]
        return self.client.post("/login", data={"action": action, "username": username, "password": password, "csrf_token": token})

    def media_url(self):
        self.login()
        data = self.get("/api/list_mp3?category=public").json
        key = next(item["play"] for item in data if item["display"].endswith(".mp3"))
        return "/mp3?category=public&playname=" + key

    def test_login_pages_and_health(self):
        self.assertEqual(self.get("/login").status_code, 200)
        self.assertEqual(self.get("/help.html").status_code, 200)
        self.assertEqual(self.get("/healthz").json["status"], "ok")
        self.assertEqual(self.get("/").status_code, 302)
        self.assertEqual(self.get("/api/list_mp3").status_code, 401)

    def test_passwords_and_csrf(self):
        self.assertEqual(self.client.post("/login", data={"username": "demo", "password": "demo-pass"}).status_code, 400)
        self.assertEqual(self.client.post("/login", data={"csrf_token": "错误"}).status_code, 400)
        self.assertIn("用户名".encode(), self.login(password="incorrect").data)
        self.assertEqual(self.login().status_code, 302)
        self.assertEqual(self.get("/").status_code, 200)

    def test_public_login_and_directory_permissions(self):
        self.assertEqual(self.login(action="公共账号登录", username="", password="").status_code, 302)
        self.assertEqual(self.get("/api/list_mp3?category=private").status_code, 403)
        self.assertEqual(self.get("/mp3?category=private&playname=x").status_code, 403)
        self.application.config["PUBLIC_CATEGORIES"] = ""
        self.assertEqual(self.get("/api/list_mp3?category=public").status_code, 403)

    def test_account_permissions_are_rechecked(self):
        self.login()
        self.userfile.write_text("demo:demo-pass:private\n", encoding="utf-8")
        self.assertEqual(self.get("/api/list_mp3?category=public").status_code, 403)

    def test_history_is_admin_only_and_excludes_passwords(self):
        self.login()
        self.get("/api/list_mp3?category=public")
        self.assertEqual(self.get("/history").status_code, 302)
        self.assertEqual(self.login(action="管理员登录", username="demo-admin", password="demo-admin-pass").status_code, 302)
        history = self.get("/history")
        self.assertEqual(history.status_code, 200)
        self.assertIn("列表:public".encode(), history.data)
        self.assertNotIn(b"demo-pass", (self.root / "data" / "history.json").read_bytes())

    def test_media_listing_filters_extensions(self):
        self.login()
        playlist = self.get("/api/list_mp3?category=public").json
        self.assertEqual(len(playlist), 2)
        self.assertTrue(all(item["play"].endswith((".mp3", ".mp4")) for item in playlist))

    def test_empty_directory_and_refresh(self):
        self.userfile.write_text("demo:demo-pass:public,private", encoding="utf-8")
        self.login()
        self.assertEqual(self.get("/api/list_mp3?category=private").json, [])
        self.assertEqual(len(self.get("/api/list_mp3?category=public").json), 2)
        (self.root / "media" / "music" / "new.mp3").write_bytes(b"new")
        self.assertEqual(len(self.get("/api/list_mp3?category=public&force=1").json), 3)

    def test_local_range_and_head(self):
        url = self.media_url()
        response = self.get(url, headers={"Range": "bytes=2-5"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.data, b"2345")
        self.assertEqual(response.headers["Content-Range"], "bytes 2-5/10")
        self.assertEqual(self.get(url, headers={"Range": "bytes=-3"}).data, b"789")
        head = self.client.head(url)
        self.addCleanup(head.close)
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.data, b"")
        self.assertEqual(head.content_length, 10)
        self.assertEqual(self.get(url, headers={"Range": "bytes=99-"}).status_code, 416)

    def test_bad_file_key_does_not_escape_media_root(self):
        self.login()
        self.assertEqual(self.get("/mp3?category=public&playname=../../app.py").status_code, 404)
        self.assertEqual(self.get("/mp3?category=public").status_code, 400)
        self.mapfile.write_text(json.dumps({"public": "../private"}), encoding="utf-8")
        self.assertEqual(self.get("/api/list_mp3?category=public&force=1").status_code, 503)

    def test_users_see_different_directories(self):
        self.userfile.write_text("demo:demo-pass:public\nreader:reader-pass:private\n", encoding="utf-8")
        self.login(username="demo", password="demo-pass")
        self.assertEqual(self.get("/api/list_mp3?category=public").status_code, 200)
        self.assertEqual(self.get("/api/list_mp3?category=private").status_code, 403)
        self.client.get("/logout")
        self.login(username="reader", password="reader-pass")
        self.assertEqual(self.get("/api/list_mp3?category=private").status_code, 200)
        self.assertEqual(self.get("/api/list_mp3?category=public").status_code, 403)



if __name__ == "__main__":
    unittest.main()
