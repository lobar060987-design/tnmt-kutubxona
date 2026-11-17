"""Online kutubxona serveri: kitoblar bazasi, o'quvchi API, admin, PDF yuklash."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import sys
import time
import uuid
from contextlib import closing
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE = Path(__file__).resolve().parent


def _load_env() -> None:
    """.env faylini o'qiydi (tashqi kutubxonasiz)."""
    f = BASE / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

PROD = os.getenv("APP_ENV", "development").lower() == "production"
DATA = Path(os.getenv("DATA_DIR", BASE / "data"))
UPLOADS = DATA / "uploads"
DB_PATH = DATA / "library.db"
SITE_NAME = os.getenv("SITE_NAME", "Online kutubxona")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
MAX_BYTES = int(os.getenv("MAX_PDF_MB", "100")) * 1024 * 1024
TOKEN_TTL = 12 * 3600
COOKIE = "kutubxona_admin"
WEAK = {"admin123", "admin", "password", "12345678", "1234567890", "BU_YERGA_KUCHLI_PAROL"}

DATA.mkdir(parents=True, exist_ok=True)
UPLOADS.mkdir(parents=True, exist_ok=True)


def _secret() -> bytes:
    """SECRET_KEY berilmasa, data/secret.key da bir marta yaratiladi va saqlanadi."""
    env = os.getenv("SECRET_KEY", "")
    if env and env != "BU_YERGA_UZUN_TASODIFIY_MATN":
        return env.encode()
    f = DATA / "secret.key"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
        try:
            f.chmod(0o600)
        except OSError:
            pass
    return f.read_text().strip().encode()


SECRET = _secret()

if ADMIN_PASSWORD in WEAK or len(ADMIN_PASSWORD) < 10:
    msg = "ADMIN_PASSWORD kuchsiz: kamida 10 belgi bo'lsin va standart parol bo'lmasin."
    if PROD:
        sys.exit("XATO: " + msg)
    print("OGOHLANTIRISH:", msg, "(serverga joylashda bu xato bo'ladi)")


# ---------- baza ----------
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.create_function("lc", 1, lambda s: norm(s))
    return conn


def norm(s: Optional[str]) -> str:
    """Kichik harf + o'zbekcha apostroflarni bitta ko'rinishga keltirish (o', g', ʻ, ’ ...)."""
    s = (s or "").lower()
    for ch in "ʻʼ‘’`´":
        s = s.replace(ch, "'")
    return s


def init_db() -> None:
    with closing(get_db()) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            """CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'Boshqa',
                year INTEGER,
                description TEXT NOT NULL DEFAULT '',
                pdf_file TEXT NOT NULL,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )"""
        )
        cols = {r["name"] for r in db.execute("PRAGMA table_info(books)")}
        if "views" not in cols:  # eski bazani buzmasdan yangilash
            db.execute("ALTER TABLE books ADD COLUMN views INTEGER NOT NULL DEFAULT 0")
        db.execute("CREATE INDEX IF NOT EXISTS idx_books_category ON books(category)")
        db.commit()


init_db()


def book_out(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "title": r["title"],
        "author": r["author"],
        "category": r["category"],
        "year": r["year"],
        "description": r["description"],
        "size_mb": round(r["size_bytes"] / 1048576, 1),
        "views": r["views"],
        "pdf_url": f"/files/{r['pdf_file']}",
    }


# ---------- admin kirishi ----------
def _sign(msg: str) -> str:
    return hmac.new(SECRET, msg.encode(), hashlib.sha256).hexdigest()


def make_token() -> str:
    exp = str(int(time.time()) + TOKEN_TTL)
    return f"{exp}.{_sign(exp)}"


def valid_token(tok: Optional[str]) -> bool:
    try:
        exp, sig = (tok or "").split(".", 1)
        return hmac.compare_digest(sig, _sign(exp)) and int(exp) > time.time()
    except ValueError:
        return False


def require_admin(request: Request) -> None:
    if not valid_token(request.cookies.get(COOKIE)):
        raise HTTPException(401, "Kirish talab qilinadi")


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


_fails: dict[str, list[float]] = {}


def _check_rate(ip: str) -> None:
    now = time.time()
    recent = [t for t in _fails.get(ip, []) if now - t < 300]
    _fails[ip] = recent
    if len(recent) >= 5:
        raise HTTPException(429, "Juda ko'p urinish. 5 daqiqadan keyin qayta urinib ko'ring")


class Login(BaseModel):
    username: str
    password: str


# ---------- ilova ----------
app = FastAPI(title=SITE_NAME, docs_url=None, redoc_url=None, openapi_url=None)

CSP = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; worker-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; "
    "base-uri 'self'; form-action 'self'; object-src 'none'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = CSP
    p = request.url.path
    if p.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    elif p.startswith("/files/") or p.startswith("/vendor/"):
        resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    elif p == "/sw.js":
        resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/api/health")
def health():
    with closing(get_db()) as db:
        db.execute("SELECT 1").fetchone()
    return {"ok": True}


@app.get("/api/config")
def config():
    return {"site_name": SITE_NAME}


@app.get("/api/stats")
def stats():
    with closing(get_db()) as db:
        b = db.execute("SELECT COUNT(*) n, COALESCE(SUM(views),0) v FROM books").fetchone()
        c = db.execute("SELECT COUNT(DISTINCT category) n FROM books").fetchone()
    return {"books": b["n"], "categories": c["n"], "views": b["v"]}


def _like(s: str) -> str:
    return "%" + norm(s).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


SORTS = {
    "new": "created_at DESC, id DESC",
    "popular": "views DESC, id DESC",
    "title": "lc(title) ASC",
    "author": "lc(author) ASC, lc(title) ASC",
}


@app.get("/api/books")
def list_books(
    q: str = "", category: str = "", sort: str = "new", limit: int = 24, offset: int = 0, ids: str = ""
):
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    where, args = "WHERE 1=1", []
    if q.strip():
        where += " AND (lc(title) LIKE ? ESCAPE '\\' OR lc(author) LIKE ? ESCAPE '\\' OR lc(category) LIKE ? ESCAPE '\\')"
        args += [_like(q.strip())] * 3
    if category:
        where += " AND category = ?"
        args.append(category)
    if ids.strip():
        idl = [int(x) for x in ids.split(",")[:200] if x.strip().isdigit()]
        if not idl:
            return {"total": 0, "items": []}
        where += f" AND id IN ({','.join('?' * len(idl))})"
        args += idl
    order = SORTS.get(sort, SORTS["new"])
    with closing(get_db()) as db:
        total = db.execute(f"SELECT COUNT(*) FROM books {where}", args).fetchone()[0]
        rows = db.execute(f"SELECT * FROM books {where} ORDER BY {order} LIMIT ? OFFSET ?", args + [limit, offset]).fetchall()
    return {"total": total, "items": [book_out(r) for r in rows]}


@app.get("/api/categories")
def categories():
    with closing(get_db()) as db:
        rows = db.execute(
            "SELECT category, COUNT(*) AS n FROM books GROUP BY category ORDER BY n DESC, category"
        ).fetchall()
    return [{"name": r["category"], "count": r["n"]} for r in rows]


@app.get("/api/books/{book_id}")
def get_book(book_id: int):
    with closing(get_db()) as db:
        r = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if not r:
        raise HTTPException(404, "Kitob topilmadi")
    return book_out(r)


_seen: dict[tuple[str, int], float] = {}


@app.post("/api/books/{book_id}/view")
def count_view(book_id: int, request: Request):
    """Bir qurilma bir kitobni 1 soatda bir marta hisoblanadi (aldab ko'paytirib bo'lmasin)."""
    key, now = (client_ip(request), book_id), time.time()
    if len(_seen) > 5000:
        for k in [k for k, t in _seen.items() if now - t > 3600]:
            _seen.pop(k, None)
    if now - _seen.get(key, 0) > 3600:
        _seen[key] = now
        with closing(get_db()) as db:
            db.execute("UPDATE books SET views = views + 1 WHERE id = ?", (book_id,))
            db.commit()
    return {"ok": True}


@app.post("/api/admin/login")
def login(body: Login, request: Request, response: Response):
    ip = client_ip(request)
    _check_rate(ip)
    ok = hmac.compare_digest(body.username.encode(), ADMIN_USER.encode()) & hmac.compare_digest(
        body.password.encode(), ADMIN_PASSWORD.encode()
    )
    if not ok:
        _fails.setdefault(ip, []).append(time.time())
        raise HTTPException(401, "Login yoki parol noto'g'ri")
    _fails.pop(ip, None)
    response.set_cookie(
        COOKIE, make_token(), max_age=TOKEN_TTL, httponly=True, samesite="lax",
        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
    )
    return {"ok": True}


@app.post("/api/admin/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/admin/check", dependencies=[Depends(require_admin)])
def check():
    return {"ok": True}


@app.get("/api/admin/stats", dependencies=[Depends(require_admin)])
def admin_stats():
    with closing(get_db()) as db:
        t = db.execute("SELECT COUNT(*) n, COALESCE(SUM(views),0) v, COALESCE(SUM(size_bytes),0) s FROM books").fetchone()
        top = db.execute("SELECT id,title,views FROM books WHERE views>0 ORDER BY views DESC LIMIT 5").fetchall()
    return {
        "books": t["n"], "views": t["v"], "size_mb": round(t["s"] / 1048576, 1),
        "top": [{"id": r["id"], "title": r["title"], "views": r["views"]} for r in top],
    }


def _clean(title: str, author: str, category: str, year: str, description: str) -> dict:
    title, author = title.strip(), author.strip()
    category = category.strip() or "Boshqa"
    if not title:
        raise HTTPException(400, "Kitob nomini kiriting")
    if len(title) > 200 or len(author) > 150 or len(category) > 60 or len(description) > 2000:
        raise HTTPException(400, "Matn juda uzun")
    y = None
    if year.strip():
        if not year.strip().isdigit() or not 1000 <= int(year) <= 2100:
            raise HTTPException(400, "Yilni to'g'ri kiriting (masalan 2019)")
        y = int(year)
    return dict(title=title, author=author, category=category, year=y, description=description.strip())


async def save_pdf(file: UploadFile) -> tuple[str, int]:
    name = f"{uuid.uuid4().hex}.pdf"
    path = UPLOADS / name
    size, first = 0, True
    try:
        with open(path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                if first:
                    if b"%PDF-" not in chunk[:1024]:
                        raise HTTPException(400, "Bu fayl PDF emas")
                    first = False
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, f"Fayl {MAX_BYTES // 1048576} MB dan katta")
                f.write(chunk)
        if size == 0:
            raise HTTPException(400, "Fayl bo'sh")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return name, size


@app.post("/api/admin/books", dependencies=[Depends(require_admin)])
async def add_book(
    title: str = Form(""), author: str = Form(""), category: str = Form("Boshqa"),
    year: str = Form(""), description: str = Form(""), pdf: UploadFile = File(...),
):
    d = _clean(title, author, category, year, description)
    name, size = await save_pdf(pdf)
    with closing(get_db()) as db:
        cur = db.execute(
            "INSERT INTO books(title,author,category,year,description,pdf_file,size_bytes,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (d["title"], d["author"], d["category"], d["year"], d["description"], name, size, int(time.time())),
        )
        db.commit()
        r = db.execute("SELECT * FROM books WHERE id=?", (cur.lastrowid,)).fetchone()
    return book_out(r)


@app.put("/api/admin/books/{book_id}", dependencies=[Depends(require_admin)])
async def edit_book(
    book_id: int, title: str = Form(""), author: str = Form(""), category: str = Form("Boshqa"),
    year: str = Form(""), description: str = Form(""), pdf: Optional[UploadFile] = File(None),
):
    d = _clean(title, author, category, year, description)
    with closing(get_db()) as db:
        old = db.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        if not old:
            raise HTTPException(404, "Kitob topilmadi")
        name, size = old["pdf_file"], old["size_bytes"]
        replaced = False
        if pdf is not None and pdf.filename:
            name, size = await save_pdf(pdf)
            replaced = True
        db.execute(
            "UPDATE books SET title=?,author=?,category=?,year=?,description=?,pdf_file=?,size_bytes=? WHERE id=?",
            (d["title"], d["author"], d["category"], d["year"], d["description"], name, size, book_id),
        )
        db.commit()
        r = db.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    if replaced:
        (UPLOADS / old["pdf_file"]).unlink(missing_ok=True)
    return book_out(r)


@app.delete("/api/admin/books/{book_id}", dependencies=[Depends(require_admin)])
def delete_book(book_id: int):
    with closing(get_db()) as db:
        r = db.execute("SELECT pdf_file FROM books WHERE id=?", (book_id,)).fetchone()
        if not r:
            raise HTTPException(404, "Kitob topilmadi")
        db.execute("DELETE FROM books WHERE id=?", (book_id,))
        db.commit()
    (UPLOADS / r["pdf_file"]).unlink(missing_ok=True)
    return {"ok": True}


@app.exception_handler(404)
async def not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": getattr(exc, "detail", "Topilmadi")}, status_code=404)
    return FileResponse(BASE / "static" / "404.html", status_code=404)


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
def api_not_found(rest: str):
    raise HTTPException(404, "Bunday API yo'q")


@app.get("/admin")
@app.get("/admin.html")
def admin_page():
    return FileResponse(BASE / "static" / "admin.html")


class PdfFiles(StaticFiles):
    """Yuklab olish uchun ?download=1 qo'llab-quvvatlanadi."""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if b"download=1" in scope.get("query_string", b""):
            resp.headers["Content-Disposition"] = 'attachment; filename="kitob.pdf"'
        return resp


app.mount("/files", PdfFiles(directory=UPLOADS), name="files")
app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
