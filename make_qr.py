"""QR kod yaratish.

Ishlatish:
    python make_qr.py https://sizning-sayt.uz

Natija: qr.png (ekran/chop uchun) va qr.svg (katta plakat uchun, sifat yo'qolmaydi).
"""
import sys

import qrcode
import qrcode.image.svg

if len(sys.argv) != 2 or not sys.argv[1].startswith("http"):
    sys.exit("Ishlatish: python make_qr.py https://sizning-sayt.uz")

url = sys.argv[1]
qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=20, border=4)
qr.add_data(url)
qr.make(fit=True)
qr.make_image(fill_color="black", back_color="white").save("qr.png")
qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, error_correction=qrcode.constants.ERROR_CORRECT_Q).save("qr.svg")
print(f"Tayyor: qr.png va qr.svg ({url})")
