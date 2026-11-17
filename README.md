# Online kutubxona

Texnikum o'quvchilari uchun kutubxona: kitoblar ro'yxati, qidiruv, PDF o'qish, admin panel, QR kod. Sayt va server bitta dastur (`main.py`).

## Nima bor

**O'quvchi paneli** (`/`): qidiruv (o', g' belgilari har xil yozilsa ham topadi), bo'limlar, saralash, "Saqlanganlar", "Davom ettirish" (qaysi sahifada to'xtagan bo'lsa), "Ko'p o'qilayotganlar", kitob oynasi, ulashish, tun rejimi, telefonga o'rnatish (PWA).
**O'qish oynasi** (`/reader.html?id=1`): sahifalar kerak bo'lganda chiziladi (katta PDF ham telefonda tez), kattalashtirish, sahifaga o'tish, oxirgi sahifani eslab qoladi. PDF.js sayt ichida, tashqi internet kerak emas.
**Admin panel** (`/admin`): kitob qo'shish, tahrirlash, o'chirish, statistika (nechta marta o'qilgani).

## Kompyuterda ishga tushirish (Windows)

`start.bat` ni ikki marta bosing. Birinchi marta parol so'raydi. Sayt: http://localhost:8000, admin: http://localhost:8000/admin.

Qo'lda:
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Serverga joylash

`DEPLOY.md` ni oching (VPS + domen + HTTPS, Railway, Fly.io).

## Ko'p kitobni bir yo'la yuklash

1. `books_template.csv` ni `books.csv` ga ko'chiring, Excelda to'ldiring ("CSV UTF-8").
2. PDF'larni `pdfs` papkasiga tashlang (`pdf_filename` ustuni fayl nomi bilan bir xil).
3. `python import_books.py --csv books.csv --pdfs pdfs`

## QR kod

```
python make_qr.py https://sizning-sayt.uz
```
`qr.png` va `qr.svg` hosil bo'ladi. Chop etishdan oldin telefon bilan skanerlab ko'ring.

## Testlar

```
pip install -r requirements-dev.txt
pytest
```

## Fayllar

- `main.py`: server va API
- `static/`: sayt (`index.html`+`app.js` o'quvchi paneli, `reader.*`, `admin.*`, `sw.js`, `vendor/` PDF.js)
- `Dockerfile`, `docker-compose.yml`, `Caddyfile`: serverga joylash
- `import_books.py`, `make_qr.py`, `backup.sh`
