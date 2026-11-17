import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"


def load_app(tmp, **env):
    os.environ.update({"DATA_DIR": str(tmp), "ADMIN_USER": "admin", "ADMIN_PASSWORD": "Kuchli-Parol-77", "SECRET_KEY": "", "APP_ENV": "development"})
    os.environ.update(env)
    sys.path.insert(0, str(ROOT))
    sys.modules.pop("main", None)
    return importlib.import_module("main")


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient
    m = load_app(tmp_path)
    with TestClient(m.app) as c:
        c.m = m
        yield c


def login(c, pw="Kuchli-Parol-77"):
    return c.post("/api/admin/login", json={"username": "admin", "password": pw})


def add(c, title, author="", cat="Boshqa", year="", data=PDF):
    return c.post("/api/admin/books", data={"title": title, "author": author, "category": cat, "year": year},
                  files={"pdf": ("a.pdf", data, "application/pdf")})


def test_health_and_empty(client):
    assert client.get("/api/health").json() == {"ok": True}
    assert client.get("/api/books").json() == {"total": 0, "items": []}
    assert client.get("/api/stats").json()["books"] == 0


def test_admin_required(client):
    assert client.post("/api/admin/books", data={"title": "x"}, files={"pdf": ("a.pdf", PDF)}).status_code == 401
    assert client.delete("/api/admin/books/1").status_code == 401
    assert client.get("/api/admin/stats").status_code == 401
    assert login(client, "xato-parol").status_code == 401
    assert login(client).status_code == 200
    assert client.get("/api/admin/check").status_code == 200


def test_rate_limit(client):
    for _ in range(5):
        assert login(client, "x").status_code == 401
    assert login(client, "x").status_code == 429
    assert login(client).status_code == 429


def test_crud_and_validation(client):
    login(client)
    assert add(client, "Bu PDF emas", data=b"hello").status_code == 400
    assert add(client, "", data=PDF).status_code == 400
    assert add(client, "Kitob", year="abc").status_code == 400
    r = add(client, "Python asoslari", "Ali Valiyev", "Dasturlash", "2021")
    assert r.status_code == 200
    b = r.json()
    assert b["year"] == 2021 and b["pdf_url"].startswith("/files/")
    assert client.get(b["pdf_url"]).content.startswith(b"%PDF-")
    assert "attachment" in client.get(b["pdf_url"] + "?download=1").headers["content-disposition"]
    e = client.put(f"/api/admin/books/{b['id']}", data={"title": "Python 2", "author": "Ali", "category": "IT"})
    assert e.json()["title"] == "Python 2" and e.json()["pdf_url"] == b["pdf_url"]
    assert client.delete(f"/api/admin/books/{b['id']}").status_code == 200
    assert client.get(b["pdf_url"]).status_code == 404
    assert client.get(f"/api/books/{b['id']}").status_code == 404


def test_search_sort_pages_ids(client):
    login(client)
    ids = [add(client, t, a, c).json()["id"] for t, a, c in [
        ("Navoiy g'azallari", "Alisher Navoiy", "Adabiyot"), ("Algebra", "Mirzo", "Matematika"),
        ("Python", "Guido", "Dasturlash"), ("Ona tili", "Karim", "Adabiyot")]]
    j = lambda u: client.get(u).json()
    assert j("/api/books?q=navoiy")["total"] == 1
    assert j("/api/books?q=NAVOIY")["total"] == 1
    assert j("/api/books?q=g‘azal")["total"] == 1  # boshqa apostrof ko'rinishi ham topadi
    assert j("/api/books?q=g%60azal")["total"] == 1
    assert j("/api/books?category=Adabiyot")["total"] == 2
    assert j("/api/books?q=100%25")["total"] == 0  # % belgisi hamma narsani qaytarmaydi
    t = [x["title"] for x in j("/api/books?sort=title")["items"]]
    assert t == sorted(t, key=str.lower)
    p = j("/api/books?limit=2&offset=2")
    assert p["total"] == 4 and len(p["items"]) == 2
    assert j(f"/api/books?ids={ids[1]},{ids[2]},zzz")["total"] == 2
    assert j("/api/books?ids=zzz")["total"] == 0
    cats = {c["name"]: c["count"] for c in j("/api/categories")}
    assert cats == {"Adabiyot": 2, "Matematika": 1, "Dasturlash": 1}


def test_views_dedupe(client):
    login(client)
    bid = add(client, "Kitob").json()["id"]
    for _ in range(3):
        client.post(f"/api/books/{bid}/view")
    assert client.get(f"/api/books/{bid}").json()["views"] == 1
    assert client.get("/api/admin/stats").json()["views"] == 1


def test_static_and_headers(client):
    for p in ["/", "/reader.html", "/admin", "/admin.html", "/app.js", "/sw.js", "/manifest.webmanifest", "/vendor/pdf.min.js", "/vendor/pdf.worker.min.js", "/icon-192.png"]:
        assert client.get(p).status_code == 200, p
    r = client.get("/")
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/api/books").headers["cache-control"] == "no-store"
    assert client.get("/yoq-sahifa").status_code == 404
    assert client.get("/api/yoq").json()["detail"]
    assert client.get("/docs").status_code == 404


def test_no_inline_scripts():
    for f in (ROOT / "static").glob("*.html"):
        t = f.read_text(encoding="utf-8")
        import re
        for m in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>", t):
            raise AssertionError(f"{f.name}: inline script (CSP bloklaydi)")
        assert " onclick=" not in t and " onload=" not in t, f.name


def test_old_db_migrates(tmp_path):
    import sqlite3
    (tmp_path / "uploads").mkdir()
    db = sqlite3.connect(tmp_path / "library.db")
    db.execute("CREATE TABLE books (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,author TEXT NOT NULL DEFAULT '',category TEXT NOT NULL DEFAULT 'Boshqa',year INTEGER,description TEXT NOT NULL DEFAULT '',pdf_file TEXT NOT NULL,size_bytes INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL)")
    db.execute("INSERT INTO books(title,pdf_file,created_at) VALUES('Eski','x.pdf',1)")
    db.commit(); db.close()
    from fastapi.testclient import TestClient
    m = load_app(tmp_path)
    with TestClient(m.app) as c:
        assert c.get("/api/books").json()["items"][0]["views"] == 0


def test_production_rejects_weak_password(tmp_path):
    with pytest.raises(SystemExit):
        load_app(tmp_path, APP_ENV="production", ADMIN_PASSWORD="admin123")
    load_app(tmp_path, APP_ENV="production", ADMIN_PASSWORD="Juda-Kuchli-77")  # kuchli parol: xato yo'q


def test_secret_persists(tmp_path):
    m1 = load_app(tmp_path)
    s1 = m1.SECRET
    m2 = load_app(tmp_path)
    assert m1.SECRET == m2.SECRET == s1 and (tmp_path / "secret.key").exists()
