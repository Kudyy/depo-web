from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Dict, Any, List, Optional
from datetime import datetime
import csv
import io
import json
import os

# Proje modülleri
from api import read_orders, save_orders_to_json, entegrabilisim_get_all_orders, merge_and_save_orders
from utils import unique_list, calc_days_ago, get_hour, delete_order, add_to_done_orders
from invoice import print_invoice_direct
from depo import get_depo_urunler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
LOCATIONS_PATH = os.path.join(BASE_DIR, "locations.csv")

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ---------- Yardımcılar ----------

def _parse_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("1","true","on","yes","evet")

def _load_locations() -> Dict[str, str]:
    locs: Dict[str,str] = {}
    if os.path.exists(LOCATIONS_PATH):
        with open(LOCATIONS_PATH, "r", encoding="utf-8", newline="") as f:
            r = csv.reader(f)
            for row in r:
                if len(row) >= 2:
                    name, location = row[0], row[1]
                    if name:
                        locs[name] = location
    return locs

def _save_locations(locs: Dict[str,str]) -> None:
    with open(LOCATIONS_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for k,v in sorted(locs.items()):
            w.writerow([k, v])

def _status(o: Dict[str,Any]) -> str:
    return (o.get("store_order_status_name") or "").lower()

def _order_color_and_days(dt_str: str) -> Dict[str,str]:
    # masaüstündeki mantık
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        hours = (now - dt).total_seconds()/3600
        saat = dt.hour
    except:
        hours = 0
        saat = 0
    if hours >= 24:
        color = "#c62828"
    elif hours >= 16:
        color = "#f8bb53"
    elif saat < 12:
        color = "#f87171"
    else:
        color = "#5bc980"
    return {"_color": color, "_days_ago": calc_days_ago(dt_str)}

def _enrich_orders(orders: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    out = []
    for o in orders:
        extra = _order_color_and_days(o.get("datetime",""))
        oo = {**o, **extra}
        out.append(oo)
    return out

# ---------- Sayfalar ----------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request,
                durum: str = "TÜMÜ",
                platform: str = "TÜMÜ",
                kargo: str = "TÜMÜ",
                t1: str = "",
                t2: str = ""):
    orders = read_orders()

    # İptaller Tümü'nde görünmesin
    if durum == "TÜMÜ":
        orders = [o for o in orders if "iptal" not in _status(o)]
    else:
        durum_map = {
            "Depodaki Siparişler": ["depoda", "depodaki siparişler"],
            "Devam Eden Siparişler": ["devam ediyor", "hazırlanıyor"],
            "Kargoya Verilecek Siparişler": ["kargoya verilecek", "kargoya verildi"],
            "Tamamlanan Siparişler": ["teslim edildi", "tamamlandı", "tamamlanan"],
            "İptal Edilen Siparişler": ["iptal", "iptal edildi"]
        }
        needles = [s.lower() for s in durum_map.get(durum, [])]
        if needles:
            orders = [o for o in orders if any(n in _status(o) for n in needles)]

    if platform != "TÜMÜ":
        orders = [o for o in orders if o.get("entegration","") == platform]
    if kargo != "TÜMÜ":
        orders = [o for o in orders if o.get("cargo_company","") == kargo]

    try:
        d1 = datetime.strptime(t1, "%d.%m.%Y") if t1 else None
    except: d1 = None
    try:
        d2 = datetime.strptime(t2, "%d.%m.%Y") if t2 else None
    except: d2 = None
    if d1:
        orders = [o for o in orders if datetime.strptime(o.get("datetime",""), "%Y-%m-%d %H:%M:%S") >= d1]
    if d2:
        orders = [o for o in orders if datetime.strptime(o.get("datetime",""), "%Y-%m-%d %H:%M:%S") <= d2]

    platformlar = unique_list([str(o.get("entegration","")) for o in read_orders() if o.get("entegration","")])
    kargolar   = unique_list([str(o.get("cargo_company","")) for o in read_orders() if o.get("cargo_company","")])

    orders = _enrich_orders(orders)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "orders": orders,
        "platformlar": platformlar,
        "kargolar": kargolar,
        "durum": durum, "platform": platform, "kargo": kargo,
        "t1": t1, "t2": t2
    })

@app.post("/refresh")
async def refresh():
    news = entegrabilisim_get_all_orders()
    merge_and_save_orders(news)
    return PlainTextResponse("ok")

# ---------- Sipariş Detayı ----------

def _find_order(no: str) -> Optional[Dict[str,Any]]:
    for o in read_orders():
        if str(o.get("no")) == str(no) or str(o.get("order_number")) == str(no):
            return o
    return None

@app.get("/order/{no}", response_class=HTMLResponse)
async def order_detail(request: Request, no: str):
    order = _find_order(no)
    if not order:
        return HTMLResponse("Sipariş bulunamadı", status_code=404)
    order = {**order, **_order_color_and_days(order.get("datetime",""))}
    # Ürünlere depo_yeri ekle
    locs = _load_locations()
    for u in order.get("order_product", []):
        u["depo_yeri"] = locs.get(u.get("name",""), None)
    return templates.TemplateResponse("depo.html", {"request": request, "order": order})

@app.post("/order/{no}/toggle")
async def toggle_item(no: str, request: Request):
    # Hem JSON hem form yakala
    try:
        data = await request.json()
    except:
        form = await request.form()
        data = dict(form)

    barcode = data.get("barcode")
    value   = _parse_bool(data.get("value"))

    orders = read_orders()
    changed = False
    for o in orders:
        if str(o.get("no")) == str(no) or str(o.get("order_number")) == str(no):
            for u in o.get("order_product", []):
                if str(u.get("barcode")) == str(barcode):
                    u["collected"] = value
                    changed = True
    if changed:
        save_orders_to_json(orders)
    return PlainTextResponse("ok")

@app.post("/order/{no}/cancel")
async def order_cancel(no: str):
    orders = read_orders()
    for o in orders:
        if str(o.get("no")) == str(no) or str(o.get("order_number")) == str(no):
            o["store_order_status"] = "-1"
            o["store_order_status_name"] = "İptal Edildi"
    save_orders_to_json(orders)
    return RedirectResponse(url=f"/order/{no}", status_code=303)

@app.post("/order/{no}/print")
async def order_print(no: str):
    order = _find_order(no)
    if not order:
        return PlainTextResponse("not found", status_code=404)
    # Masaüstündeki mantığı koruyoruz:
    print_invoice_direct(order)
    delete_order(no)
    add_to_done_orders(no)
    return RedirectResponse(url="/", status_code=303)

# ---------- Depodan Toplanacaklar ----------

@app.get("/picklist", response_class=HTMLResponse)
async def picklist(request: Request, platform: str="TÜMÜ", t1: str="", t2: str="", q: str=""):
    try:
        d1 = datetime.strptime(t1, "%d.%m.%Y") if t1 else None
    except: d1 = None
    try:
        d2 = datetime.strptime(t2, "%d.%m.%Y") if t2 else None
    except: d2 = None

    urunler = get_depo_urunler(read_orders(), platform_filter=platform, date_start=d1, date_end=d2, arama_terimi=q)

    # hepsi toplandı mı?
    for u in urunler:
        all_collected = True
        for order, ud in u.get("orders", []):
            if not ud.get("collected"):
                all_collected = False
                break
        u["_collected"] = all_collected

    # depo yeri
    locs = _load_locations()
    for u in urunler:
        u["depo_yeri"] = locs.get(u.get("name",""), None)

    return templates.TemplateResponse("picklist.html", {
        "request": request, "urunler": urunler,
        "platform": platform, "t1": t1, "t2": t2, "q": q
    })

@app.post("/picklist/toggle")
async def picklist_toggle(request: Request):
    # JSON veya form
    try:
        data = await request.json()
    except:
        form = await request.form()
        data = dict(form)

    barcode = data.get("barcode")
    value   = _parse_bool(data.get("value"))

    if not barcode:
        return PlainTextResponse("missing barcode", status_code=400)

    orders = read_orders()
    for o in orders:
        for u in o.get("order_product", []):
            if str(u.get("barcode")) == str(barcode):
                u["collected"] = value
    save_orders_to_json(orders)
    return PlainTextResponse("ok")

@app.post("/picklist/set-location")
async def set_location(request: Request):
    form = await request.form()
    name = (form.get("name") or "").strip()
    location = (form.get("location") or "").strip()
    if not name:
        return PlainTextResponse("name required", status_code=400)
    locs = _load_locations()
    locs[name] = location
    _save_locations(locs)
    return PlainTextResponse("ok")

# ---------- Depo Yerleri ----------

@app.get("/locations", response_class=HTMLResponse)
async def locations_page(request: Request, q: str = ""):
    locs = _load_locations()
    items = [{"name": k, "location": v} for k,v in locs.items()]
    if q:
        items = [it for it in items if q.lower() in it["name"].lower()]
    items.sort(key=lambda x: x["name"])
    return templates.TemplateResponse("locations.html", {"request": request, "items": items, "q": q})

@app.post("/locations/set")
async def locations_set(name: str = Form(...), location: str = Form(...)):
    locs = _load_locations()
    locs[name] = location
    _save_locations(locs)
    return RedirectResponse(url="/locations", status_code=303)

@app.post("/locations/import")
async def locations_import(file: UploadFile = File(...)):
    contents = await file.read()
    s = contents.decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(s))
    locs = _load_locations()
    for row in reader:
        if len(row) >= 2:
            locs[row[0]] = row[1]
    _save_locations(locs)
    return RedirectResponse(url="/locations", status_code=303)

@app.get("/locations/export")
async def locations_export():
    locs = _load_locations()
    buf = io.StringIO()
    w = csv.writer(buf)
    for k,v in sorted(locs.items()):
        w.writerow([k,v])
    data = buf.getvalue().encode("utf-8")
    return StreamingResponse(io.BytesIO(data),
                             media_type="text/csv",
                             headers={"Content-Disposition":"attachment; filename=locations.csv"})