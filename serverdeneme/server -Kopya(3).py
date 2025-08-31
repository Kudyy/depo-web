# server.py  (FastAPI)
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response
import json, csv, io
from datetime import datetime
from typing import Dict, Any, List, Optional

from api import read_orders, save_orders_to_json
from utils import unique_list, calc_days_ago, delete_order, add_to_done_orders
from depo import get_depo_urunler

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates("templates")

OUTPUT_JSON = "output.json"
LOCATIONS_JSON = "locations.json"

# ---------- yardımcılar ----------
def load_locations() -> Dict[str, str]:
    try:
        with open(LOCATIONS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_locations(d: Dict[str, str]) -> None:
    with open(LOCATIONS_JSON, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def _color_for(order_dt: str) -> str:
    try:
        dt = datetime.strptime(order_dt, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        hours = (now - dt).total_seconds() / 3600
        if hours >= 24:
            return "#c62828"
        elif hours >= 16:
            return "#f8bb53"
        elif dt.hour < 12:
            return "#f87171"
        else:
            return "#5bc980"
    except:
        return "#5bc980"

def hydrate_orders(orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for o in orders:
        o["_days_ago"] = calc_days_ago(o.get("datetime", ""))
        o["_color"] = _color_for(o.get("datetime", ""))
    return orders

def write_orders(orders: List[Dict[str, Any]]) -> None:
    save_orders_to_json(orders)

# ---------- sayfalar ----------
@app.get("/", response_class=HTMLResponse)
def index(request: Request,
          durum: str = "TÜMÜ",
          platform: str = "TÜMÜ",
          kargo: str = "TÜMÜ",
          t1: str = "",
          t2: str = ""):
    orders = read_orders()

    if durum == "TÜMÜ":
        orders = [o for o in orders if "iptal" not in (o.get("store_order_status_name","").lower())]
    else:
        durum_map = {
            "Depodaki Siparişler": ["depoda"],
            "Devam Eden Siparişler": ["devam", "hazırlanıyor"],
            "Kargoya Verilecek Siparişler": ["kargoya verilecek", "kargoya verildi"],
            "Tamamlanan Siparişler": ["teslim", "tamam"],
            "İptal Edilen Siparişler": ["iptal"]
        }
        anahtarlar = durum_map.get(durum, [])
        orders = [o for o in orders if any(k in (o.get("store_order_status_name","").lower()) for k in anahtarlar)]

    if platform != "TÜMÜ":
        orders = [o for o in orders if o.get("entegration","") == platform]
    if kargo != "TÜMÜ":
        orders = [o for o in orders if o.get("cargo_company","") == kargo]

    d1 = datetime.strptime(t1, "%d.%m.%Y") if t1 else None
    d2 = datetime.strptime(t2, "%d.%m.%Y") if t2 else None
    if d1: orders = [o for o in orders if datetime.strptime(o.get("datetime",""), "%Y-%m-%d %H:%M:%S") >= d1]
    if d2: orders = [o for o in orders if datetime.strptime(o.get("datetime",""), "%Y-%m-%d %H:%M:%S") <= d2]

    platformlar = unique_list([o.get("entegration","") for o in read_orders() if o.get("entegration","")])
    kargolar   = unique_list([o.get("cargo_company","") for o in read_orders() if o.get("cargo_company","")])

    return templates.TemplateResponse(
        "index.html",
        {"request": request,
         "orders": hydrate_orders(orders),
         "platformlar": platformlar,
         "kargolar": kargolar,
         "durum": durum, "platform": platform, "kargo": kargo,
         "t1": t1, "t2": t2}
    )

@app.get("/order/{order_no}", response_class=HTMLResponse)
def order_detail(request: Request, order_no: str):
    orders = read_orders()
    order = next((o for o in orders if str(o.get("no")) == str(order_no)), None)
    if not order:
        return PlainTextResponse("Not Found", status_code=404)
    return templates.TemplateResponse("depo.html", {"request": request, "order": {**order, "_color": _color_for(order.get("datetime",""))}})

# ---------- Ortak toggle endpoint ----------
@app.post("/toggle-collected")
def toggle_collected(barcode: str = Form(...), value: Optional[str] = Form(None), order_no: Optional[str] = Form(None)):
    """
    Barkod üzerinden tüm siparişlerdeki ürünlerin 'collected' durumunu değiştirir.
    Eğer order_no verilirse sadece o siparişteki ürün etkilenir.
    """
    v = str(value).lower() in ("true", "1", "on", "yes")

    orders = read_orders()
    for o in orders:
        if order_no and str(o.get("no")) != str(order_no):
            continue
        for u in o.get("order_product", []):
            if str(u.get("barcode", "")) == str(barcode):
                u["collected"] = v
    write_orders(orders)
    return Response(status_code=204)

# İptal et
@app.post("/order/{order_no}/cancel")
def cancel_order(order_no: str):
    orders = read_orders()
    for o in orders:
        if str(o.get("no")) == str(order_no):
            o["store_order_status"] = "-1"
            o["store_order_status_name"] = "İptal Edildi"
    write_orders(orders)
    return RedirectResponse(url=f"/order/{order_no}", status_code=303)

# Onayla + fatura yazdırıldıktan sonra liste dışı
@app.post("/order/{order_no}/print")
def order_print(order_no: str):
    try:
        delete_order(order_no)
        add_to_done_orders(order_no)
    except Exception:
        pass
    return RedirectResponse(url="/", status_code=303)

# ---------- Picklist ----------
@app.get("/picklist", response_class=HTMLResponse)
def picklist(request: Request, platform: str = "TÜMÜ", t1: str = "", t2: str = "", q: str = ""):
    d1 = datetime.strptime(t1, "%d.%m.%Y") if t1 else None
    d2 = datetime.strptime(t2, "%d.%m.%Y") if t2 else None

    urunler = get_depo_urunler(read_orders(), platform, d1, d2, q)

    locs = load_locations()
    filtered = []
    for u in urunler:
        u["depo_yeri"] = locs.get(u["name"], "")
        all_collected = all(pr.get("collected", False) for (o, pr) in u.get("orders", []))
        u["_collected"] = all_collected
        # Sadece toplanmamış ürünleri göster
        if not all_collected:
            filtered.append(u)

    return templates.TemplateResponse("picklist.html",
        {"request": request, "urunler": filtered, "platform": platform, "t1": t1, "t2": t2, "q": q})

# depo yeri set
@app.post("/picklist/set-location")
def picklist_set_location(name: str = Form(...), location: str = Form(...)):
    locs = load_locations()
    locs[name] = location.strip()
    save_locations(locs)
    return Response(status_code=204)

# ---------- Depo Yerleri ----------
@app.get("/locations", response_class=HTMLResponse)
def locations_page(request: Request, q: str = ""):
    locs = load_locations()
    items = [{"name": n, "location": l} for n,l in locs.items()]
    if q:
        low = q.lower()
        items = [it for it in items if low in it["name"].lower()]
    return templates.TemplateResponse("locations.html", {"request": request, "items": items, "q": q})

@app.post("/locations/set")
def locations_set(name: str = Form(...), location: str = Form(...)):
    locs = load_locations()
    locs[name] = location.strip()
    save_locations(locs)
    return RedirectResponse(url="/locations", status_code=303)

@app.get("/locations/export")
def locations_export():
    locs = load_locations()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name","location"])
    for k,v in locs.items():
        w.writerow([k,v])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")

@app.post("/locations/import")
def locations_import(file: UploadFile = File(...)):
    content = file.file.read().decode("utf-8", "ignore")
    locs = load_locations()
    r = csv.DictReader(io.StringIO(content))
    for row in r:
        n = row.get("name","").strip()
        l = row.get("location","").strip()
        if n:
            locs[n] = l
    save_locations(locs)
    return RedirectResponse(url="/locations", status_code=303)