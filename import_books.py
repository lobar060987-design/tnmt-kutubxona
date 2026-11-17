"""Kitoblarni CSV va PDF papkadan bir buyruqda yuklash.

Ishlatish:
    python import_books.py --csv books.csv --pdfs pdfs

CSV ustunlari: title, author, category, year, pdf_filename, description
(faqat title va pdf_filename majburiy). Excelda "CSV UTF-8" qilib saqlang.
"""
import argparse
import csv
import shutil
import sys
import time
import uuid
from contextlib import closing
from pathlib import Path

from main import UPLOADS, get_db, init_db


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="books.csv")
    ap.add_argument("--pdfs", default="pdfs")
    a = ap.parse_args()
    init_db()

    text = Path(a.csv).read_text(encoding="utf-8-sig")
    head = text.splitlines()[0] if text else ""
    delim = ";" if head.count(";") > head.count(",") else ","
    rows = list(csv.DictReader(text.splitlines(), delimiter=delim))
    pdf_dir = Path(a.pdfs)
    added = skipped = 0

    with closing(get_db()) as db:
        for i, r in enumerate(rows, start=2):
            r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
            title, fname = r.get("title", ""), r.get("pdf_filename", "")
            if not title or not fname:
                print(f"{i}-qator o'tkazib yuborildi: title yoki pdf_filename bo'sh")
                skipped += 1
                continue
            src = pdf_dir / fname
            if not src.is_file():
                print(f"{i}-qator: '{fname}' fayli {pdf_dir} papkasida topilmadi")
                skipped += 1
                continue
            with open(src, "rb") as f:
                if b"%PDF-" not in f.read(1024):
                    print(f"{i}-qator: '{fname}' PDF emas")
                    skipped += 1
                    continue
            author = r.get("author", "")
            if db.execute("SELECT 1 FROM books WHERE title=? AND author=?", (title, author)).fetchone():
                print(f"{i}-qator: '{title}' allaqachon bor, o'tkazib yuborildi")
                skipped += 1
                continue
            year = r.get("year", "")
            year = int(year) if year.isdigit() and 1000 <= int(year) <= 2100 else None
            name = f"{uuid.uuid4().hex}.pdf"
            shutil.copyfile(src, UPLOADS / name)
            db.execute(
                "INSERT INTO books(title,author,category,year,description,pdf_file,size_bytes,created_at)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (title, author, r.get("category") or "Boshqa", year, r.get("description", ""),
                 name, src.stat().st_size, int(time.time())),
            )
            added += 1
        db.commit()
    print(f"Tayyor: {added} ta kitob qo'shildi, {skipped} ta o'tkazib yuborildi.")
    return 0 if added or not skipped else 1


if __name__ == "__main__":
    sys.exit(main())
