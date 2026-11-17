# Serverga joylash

Baza (`library.db`) va PDF'lar `/data` papkasida saqlanadi. Hosting **doimiy disk** bersin (VPS yaxshi). Vercel/Netlify mos emas.

## 1-usul: VPS (FirstByte va boshqalar), domen bilan. Tavsiya

Server: Ubuntu 22.04/24.04, 1 GB RAM yetadi. Domeningizning A-yozuvi server IP'siga qaralgan bo'lsin.

```bash
# 1) Docker o'rnatish (bir marta)
curl -fsSL https://get.docker.com | sh

# 2) Loyihani serverga yuklash (kompyuteringizdan: scp -r kutubxona root@SERVER_IP:/opt/)
cd /opt/kutubxona

# 3) Sozlash
cp .env.example .env
nano .env
```
`.env` ichida o'zgartiring:
```
ADMIN_PASSWORD=Kuchli-parol-yozing-123
APP_ENV=production
DOMAIN=kutubxona.sizning-domen.uz
```
```bash
# 4) Ishga tushirish (HTTPS avtomatik olinadi)
docker compose up -d --build
docker compose logs -f app      # "Uvicorn running" ko'rinsa tayyor (Ctrl+C)
```
Tekshirish: `https://DOMEN/api/health` -> `{"ok":true}`, admin: `https://DOMEN/admin`.

Domen bo'lmasa: `.env` da `DOMAIN=:80` yozing, sayt `http://SERVER_IP` da ochiladi (HTTPS bo'lmaydi, QR uchun domen yaxshiroq).

Firewall: 80 va 443 portlar ochiq bo'lsin (`ufw allow 80,443/tcp`).

### Yangilash
Yangi fayllarni yuklab: `docker compose up -d --build`. Kitoblar o'chmaydi (alohida volume).

### Zaxira nusxa
`./backup.sh` -> `zaxira-SANA.tgz` (baza, PDF'lar, secret.key). Haftada bir marta oling va boshqa joyga saqlang.
Tiklash: `docker compose run --rm --no-deps -v $(pwd):/in app sh -c 'tar xzf /in/zaxira-SANA.tgz -C /data'`

## 2-usul: faqat Docker (domensiz, proksisiz)
```bash
docker build -t kutubxona .
docker run -d --name kutubxona --restart unless-stopped -p 8000:8000 -v kutubxona_data:/data \
  -e ADMIN_PASSWORD='Kuchli-Parol-77' kutubxona
```
Oldiga HTTPS beruvchi proksi kerak (Caddy/Nginx). Katta PDF uchun proksida yuklash limitini 110 MB qiling.

## 3-usul: Railway / Fly.io
- Railway: GitHub'dan deploy, Volume qo'shing (mount: `/data`), Variables: `ADMIN_PASSWORD`, `APP_ENV=production`, `DATA_DIR=/data`.
- Fly.io: `fly.toml` dagi `app` nomini o'zgartiring, `fly volumes create kutubxona_data --size 3 --region fra`, `fly secrets set ADMIN_PASSWORD=...`, `fly deploy`.

## 4-usul: texnikum kompyuteri
`start.bat`. Telefonlar shu Wi-Fi'dan `http://KOMPYUTER-IP:8000` orqali kiradi.

## Joylashdan oldin ro'yxat
- [ ] `ADMIN_PASSWORD` kuchli (kamida 10 belgi). `APP_ENV=production` da kuchsiz parol bo'lsa server ishga tushmaydi
- [ ] `/data` doimiy diskka ulangan
- [ ] `https://DOMEN/api/health` javob beradi
- [ ] Telefonda sayt ochiladi, kitob o'qiladi
- [ ] Admin orqali kitob qo'shish/tahrirlash/o'chirish ishlaydi
- [ ] `python make_qr.py https://DOMEN` bilan QR yaratildi va skanerlab tekshirildi
- [ ] Zaxira nusxa tartibi belgilangan

## Muammo bo'lsa
- Admin kirmayapti: `docker compose logs app` ni ko'ring; 5 marta xato parol bo'lsa 5 daqiqa kuting.
- PDF yuklanmayapti: fayl 100 MB dan kichik bo'lsin (`MAX_PDF_MB`).
- Sayt eski ko'rinyapti: brauzerda Ctrl+F5.
