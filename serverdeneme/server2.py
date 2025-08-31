from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict, Any, List
from datetime import datetime
import json, csv, os

# Yerel modüller
from api import read_orders, save_orders_to_json, entegrabilisim_get_all_orders, merge_and_save_orders
from utils import calc_days_ago
try:
    from depo import get_depo_urunler
except Exception:
    get_depo_urunler = None

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

OUTPUT_JSON = "output.json"
LOCATIONS_CSV = "locations.csv"

# ----------------- Yardımcılar -----------------

def _load_orders() -> List[Dict[str, Any]]:
    return read_orders(OUTPUT_JSON)

def _save_orders(orders: List[Dict[str, Any]]):
    save_orders_to_json(orders, OUTPUT_JSON)

def _color_for_order(order: Dict[str, Any]) -> str:
    try:
        dt = datetime.strptime(order.get("datetime", ""), "%Y-%m-%d %H:%M:%S")
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
    except Exception:
        return "#5bc980"

def _enrich_order(o: Dict[str, Any]) -> Dict[str, Any]:
    o = dict(o)
    o["_color"] = _color_for_order(o)
    o["_days_ago"] = calc_days_ago(o.get("datetime", ""))
    return o

def _filter_orders(orders, durum, platform, kargo, t1, t2):
    res = orders[:]
    if durum == "TÜMÜ":
        res = [o for o in res if "iptal" not in (o.get("store_order_status_name","").lower())]
    else:
        durum_map = {
            "Depodaki Siparişler": ["depoda"],
            "Devam Eden Siparişler": ["devam", "hazırlanıyor"],
            "Kargoya Verilecek Siparişler": ["kargoya verilecek", "kargoya verildi"],
            "Tamamlanan Siparişler": ["teslim", "tamam"],
            "İptal Edilen Siparişler": ["iptal"]
        }
        anahtarlar = durum_map.get(durum, [])
        res = [o for o in res if any(k in (o.get("store_order_status_name","").lower()) for k in anahtarlar)]

    if platform != "TÜMÜ":
        res = [o for o in res if o.get("entegration","") == platform]
    if kargo != "TÜMÜ":
        res = [o for o in res if o.get("cargo_company","") == kargo]

    def _parse_tr(d):
        return datetime.strptime(d, "%d.%m.%Y")

    if t1:
        try:
            d1 = _parse_tr(t1)
            res = [o for o in res if datetime.strptime(o.get("datetime",""), "%Y-%m-%d %H:%M:%S") >= d1]
        except Exception:
            pass
    if t2:
        try:
            d2 = _parse_tr(t2)
            res = [o for o in res if datetime.strptime(o.get("datetime",""), "%Y-%m-%d %H:%M:%S") <= d2]
        except Exception:
            pass
    return res

def _toggle_collected_by_barcode(barcode: str, value: bool) -> bool:
    if not barcode:
        return False
    orders = _load_orders()
    changed = False
    for o in orders:
        for u in o.get("order_product", []):
            if str(u.get("barcode", "")) == str(barcode):
                if u.get("collected") != value:
                    u["collected"] = value
                    changed = True
    if changed:
        _save_orders(orders)
    return changed

def _toggle_order_line(order_no: str, barcode: str, value: bool) -> bool:
    orders = _load_orders()
    changed = False
    for o in orders:
        if str(o.get("no")) == str(order_no):
            for u in o.get("order_product", []):
                if str(u.get("barcode","")) == str(barcode):
                    if u.get("collected") != value:
                        u["collected"] = value
                        changed = True
            break
    if changed:
        _save_orders(orders)
    return changed

# ----------------- Sayfalar -----------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, durum="TÜMÜ", platform="TÜMÜ", kargo="TÜMÜ", t1="", t2=""):
    orders = _load_orders()
    platformlar = sorted({o.get("entegration","") for o in orders if o.get("entegration","")})
    kargolar   = sorted({o.get("cargo_company","") for o in orders if o.get("cargo_company","")})
    filt = _filter_orders(orders, durum, platform, kargo, t1.strip(), t2.strip())
    enriched = [_enrich_order(o) for o in filt]
    return templates.TemplateResponse("index.html", {
        "request": request,
        "orders": enriched,
        "platformlar": platformlar,
        "kargolar": kargolar,
        "durum": durum,
        "platform": platform,
        "kargo": kargo,
        "t1": t1,
        "t2": t2
    })

@app.get("/order/{order_no}", response_class=HTMLResponse)
async def order_detail(request: Request, order_no: str):
    orders = _load_orders()
    cur = next((o for o in orders if str(o.get("no")) == str(order_no)), None)
    if not cur:
        return HTMLResponse("<h3>404 - Sipariş bulunamadı</h3>", status_code=404)
    cur = _enrich_order(cur)
    return templates.TemplateResponse("depo.html", {"request": request, "order": cur})

@app.post("/order/{order_no}/cancel")
async def order_cancel(order_no: str):
    orders = _load_orders()
    for o in orders:
        if str(o.get("no")) == str(order_no):
            o["store_order_status"] = "-1"
            o["store_order_status_name"] = "İptal Edildi"
            break
    _save_orders(orders)
    return RedirectResponse(url=f"/order/{order_no}", status_code=303)

@app.post("/order/{order_no}/print")
async def order_print(order_no: str):
    orders = _load_orders()
    for o in orders:
        if str(o.get("no")) == str(order_no):
            o["store_order_status"] = "4"
            o["store_order_status_name"] = "Kargoya Verildi"
            break
    _save_orders(orders)
    return RedirectResponse(url=f"/order/{order_no}", status_code=303)

@app.post("/order/{order_no}/toggle")
async def order_toggle_collected(order_no: str, barcode: str = Form(...), value: str = Form(...)):
    v = str(value).lower() in ("true", "1", "on", "yes")
    ok = _toggle_order_line(order_no, barcode, v)
    return PlainTextResponse("OK" if ok else "NO-CHANGE", status_code=200)

# ----------------- Picklist (Eski Mantık) -----------------

@app.get("/picklist", response_class=HTMLResponse)
async def picklist(request: Request, platform="TÜMÜ", t1="", t2="", q=""):
    d1 = datetime.strptime(t1, "%d.%m.%Y") if t1 else None
    d2 = datetime.strptime(t2, "%d.%m.%Y") if t2 else None

    urunler = get_depo_urunler(_load_orders(), platform, d1, d2, q)

    locs = _read_locations()
    filtered = []
    for u in urunler:
        u["depo_yeri"] = locs.get(u["name"], "")
        all_collected = all(pr.get("collected", False) for (o, pr) in u.get("orders", []))
        u["_collected"] = all_collected
        if not all_collected:
            filtered.append(u)

    return templates.TemplateResponse("picklist.html", {
        "request": request,
        "urunler": filtered,
        "platform": platform,
        "t1": t1,
        "t2": t2,
        "q": q
    })

@app.post("/picklist/toggle")
async def picklist_toggle(barcode: str = Form(...), value: str = Form(...)):
    v = str(value).lower() in ("true", "1", "on", "yes")
    ok = _toggle_collected_by_barcode(barcode, v)
    return PlainTextResponse("OK" if ok else "NO-CHANGE", status_code=200)

# ----------------- Depo Yerleri -----------------

def _read_locations() -> Dict[str, str]:
    if not os.path.exists(LOCATIONS_CSV):
        return {}
    with open(LOCATIONS_CSV, "r", encoding="utf-8") as f:
        r = csv.reader(f)
        return {row[0]: row[1] for row in r if len(row) >= 2}

def _write_locations(d: Dict[str, str]):
    with open(LOCATIONS_CSV, "w", encoding="utf-8") as f:
        w = csv.writer(f)
        for k, v in sorted(d.items()):
            w.writerow([k, v])

@app.get("/locations", response_class=HTMLResponse)
async def locations_page(request: Request, q: str = ""):
    locs = _read_locations()
    items = [{"name": k, "location": v} for k, v in locs.items()]
    if q:
        items = [it for it in items if q.lower() in it["name"].lower()]
    items.sort(key=lambda x: x["name"].lower())
    return templates.TemplateResponse("locations.html", {"request": request, "items": items, "q": q})

@app.post("/locations/set")
async def locations_set(name: str = Form(...), location: str = Form(...)):
    locs = _read_locations()
    locs[name] = location.strip()
    _write_locations(locs)
    return RedirectResponse(url="/locations", status_code=303)

@app.get("/locations/export")
async def locations_export():
    if not os.path.exists(LOCATIONS_CSV):
        open(LOCATIONS_CSV, "w").close()
    with open(LOCATIONS_CSV, "r", encoding="utf-8") as f:
        content = f.read()
    return PlainTextResponse(content, media_type="text/csv")

@app.post("/locations/import")
async def locations_import(file: UploadFile = File(...)):
    content = await file.read()
    rows = [r.split(",") for r in content.decode("utf-8", "ignore").splitlines() if r.strip()]
    locs = _read_locations()
    for r in rows:
        if len(r) >= 2:
            locs[r[0].strip()] = r[1].strip()
    _write_locations(locs)
    return RedirectResponse(url="/locations", status_code=303)

# ----------------- Token & Refresh -----------------

@app.get("/token", response_class=HTMLResponse)
async def token_form(request: Request):
    cur = ""
    try:
        with open("token.txt", "r", encoding="utf-8") as f:
            cur = f.read().strip()
    except Exception:
        pass
    html = f"""<html><body><form method='post' action='/token'>
    <input name='token' value='{cur}' /><button>Kaydet</button></form></body></html>"""
    return HTMLResponse(html)

@app.post("/token")
async def token_save(token: str = Form(...)):
    with open("token.txt", "w", encoding="utf-8") as f:
        f.write(token.strip())
    return RedirectResponse(url="/token", status_code=303)

@app.post("/refresh")
async def refresh_from_api():
    new_orders = entegrabilisim_get_all_orders()
    if new_orders:
        merge_and_save_orders(new_orders, path=OUTPUT_JSON)
        return PlainTextResponse("OK", status_code=200)
    return PlainTextResponse("NO-DATA", status_code=500)