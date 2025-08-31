import tempfile
import os
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageWin
import io
import barcode
from barcode.writer import ImageWriter
import win32print
import win32ui
import win32con
from api import read_orders, save_orders_to_json
from utils import get_hour, calc_days_ago

def wrap_text(draw, text, font, max_width):
    lines = []
    words = text.split()
    line = ""
    for word in words:
        test_line = f"{line} {word}".strip()
        if draw.textlength(test_line, font=font) <= max_width:
            line = test_line
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines

def create_invoice_image(order, urun_start_index=0, max_urun_satir=10):
    width_mm, height_mm = 100, 120
    dpi = 203
    width_px = int(width_mm / 25.4 * dpi)
    height_px = int(height_mm / 25.4 * dpi)
    img = Image.new("RGB", (width_px, height_px), "white")
    draw = ImageDraw.Draw(img)
    padding = 14
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not os.path.exists(font_path):
        font_path = "C:/Windows/Fonts/arialbd.ttf"
    font_big = ImageFont.truetype(font_path, 25)
    font_med = ImageFont.truetype(font_path, 22)
    font_small = ImageFont.truetype(font_path, 18)
    font_urun = ImageFont.truetype(font_path, 20)
    font_barkod = ImageFont.truetype(font_path, 18)

    entegrasyon = (order.get("entegration") or "").lower()
    siparis_no = order.get("order_number") if entegrasyon == "hepsiburada" else order.get("no", "-")

    tablo_x = padding
    tablo_y = padding
    tablo_w = width_px - 2 * padding
    tablo_h = int(height_px * 0.28)
    draw.rectangle([tablo_x, tablo_y, tablo_x + tablo_w, tablo_y + tablo_h], outline="#333", width=2)
    sol_w = int(tablo_w * 0.52)
    sag_x = tablo_x + sol_w + 6
    draw.line([sag_x, tablo_y, sag_x, tablo_y + tablo_h], fill="#333", width=2)
    row_h = int(tablo_h / 7.2)
    labels = ["İsim", "Telefon", "Kargo", "Pazaryeri", "Sip No", "Tarih"]
    values = [
        f"{order.get('firstname','')} {order.get('lastname','')}",
        order.get("mobil_phone") or order.get("telephone") or order.get("ship_tel") or order.get("invoice_tel") or "-",
        order.get("cargo_company","-"),
        order.get("entegration","-"),
        siparis_no,
        order.get("datetime","-")
    ]
    for i, (lab, val) in enumerate(zip(labels, values)):
        y = tablo_y + i * row_h + 6
        draw.text((tablo_x + 8, y), f"{lab}:", font=font_med, fill="#111")
        draw.text((tablo_x + 105, y), str(val), font=font_big, fill="#111")

    adres = order.get("ship_address") or order.get("invoice_address") or ""
    adres_kutu_x = sag_x + 7
    adres_kutu_y = tablo_y + 4
    adres_kutu_w = tablo_x + tablo_w - adres_kutu_x - 9
    adres_kutu_h = tablo_h - 8
    draw.rectangle([adres_kutu_x, adres_kutu_y, adres_kutu_x + adres_kutu_w, adres_kutu_y + adres_kutu_h], outline="#333", width=2)
    max_adres_w = adres_kutu_w - 7
    adres_lines = wrap_text(draw, adres, font_big, max_adres_w)
    for i, line in enumerate(adres_lines[:4]):
        ay = adres_kutu_y + 5 + i*27
        draw.text((adres_kutu_x + 6, ay), line, font=font_big, fill="#111")

    barkod_val = str(order.get("cargo_code", "")).strip()
    if not barkod_val or barkod_val == "-":
        barkod_val = str(siparis_no)
    try:
        barcode_width = int(adres_kutu_w * 0.9)
        barcode_height = int(adres_kutu_h * 0.35)
        barcode_img_io = io.BytesIO()
        code = barcode.get('code128', barkod_val, writer=ImageWriter())
        code.write(barcode_img_io, options={"write_text": False})
        barcode_img_io.seek(0)
        barkod_img = Image.open(barcode_img_io)
        barkod_img = barkod_img.resize((barcode_width, barcode_height), resample=Image.LANCZOS)
        bx = adres_kutu_x + int((adres_kutu_w - barcode_width) // 2)
        by = adres_kutu_y + adres_kutu_h - barcode_height - 18
        img.paste(barkod_img, (bx, by))
        bnum_x = bx + (barcode_width//2) - (len(barkod_val)*font_barkod.size)//2
        bnum_y = by + barcode_height + 2
        draw.text((bnum_x, bnum_y), barkod_val, font=font_barkod, fill="#111")
    except Exception as e:
        draw.text((adres_kutu_x+6, adres_kutu_y+adres_kutu_h-20), barkod_val, font=font_barkod, fill="#c00")

    tablo_urun_y = tablo_y + tablo_h + 14
    draw.line([tablo_x, tablo_urun_y-8, tablo_x+tablo_w, tablo_urun_y-8], fill="#333", width=2)
    draw.text((tablo_x + 4, tablo_urun_y), "Stok Kodu", font=font_small, fill="#333")
    draw.text((tablo_x + 100, tablo_urun_y), "Ürün", font=font_small, fill="#333")
    draw.text((tablo_x + tablo_w - 60, tablo_urun_y), "Adet", font=font_small, fill="#333")

    urun_y = tablo_urun_y + 17
    max_urun_w = tablo_w - 200
    urunler = order.get("order_product", [])
    for i, urun in enumerate(urunler[urun_start_index:urun_start_index+max_urun_satir]):
        stok_kodu = str(urun.get("store_stock_code", ""))
        urun_adi = urun.get("name", "")
        miktar = str(urun.get("quantity", ""))
        sk_x = tablo_x + 4
        urun_x = sk_x + 100
        adet_x = tablo_x + tablo_w - 60
        max_stok_kodu_w = 80
        max_urun_genislik = adet_x - urun_x - 8
        stok_kodu_lines = wrap_text(draw, stok_kodu, font_urun, max_stok_kodu_w)
        urun_lines = wrap_text(draw, urun_adi, font_urun, max_urun_genislik)
        max_line_count = max(len(stok_kodu_lines), len(urun_lines))
        for lidx in range(max_line_count):
            sk_txt = stok_kodu_lines[lidx] if lidx < len(stok_kodu_lines) else ""
            ur_txt = urun_lines[lidx] if lidx < len(urun_lines) else ""
            adet_txt = miktar if lidx == 0 else ""
            draw.text((sk_x, urun_y + lidx*18), sk_txt, font=font_urun, fill="#111")
            draw.text((urun_x, urun_y + lidx*18), ur_txt, font=font_urun, fill="#111")
            draw.text((adet_x, urun_y + lidx*18), adet_txt, font=font_urun, fill="#111")
        urun_y += 18 * max_line_count

    return img

def print_invoice_direct(order, yazici_adi=None):
    invoice_img = create_invoice_image(order)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        invoice_img.save(tmp.name, dpi=(203,203))
        tmp_path = tmp.name
    if yazici_adi is None:
        yazici_adi = win32print.GetDefaultPrinter()
    hprinter = win32print.OpenPrinter(yazici_adi)
    try:
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(yazici_adi)
        hdc.StartDoc("Otomatik Fatura Yazdırma")
        hdc.StartPage()
        img = Image.open(tmp_path)
        dib = ImageWin.Dib(img)
        printer_size = hdc.GetDeviceCaps(110), hdc.GetDeviceCaps(117)
        dib.draw(hdc.GetHandleOutput(), (0, 0, printer_size[0], printer_size[1]))
        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()
    finally:
        win32print.ClosePrinter(hprinter)
        try:
            os.remove(tmp_path)
        except:
            pass
