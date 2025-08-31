# server.py
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict, Any, List
from datetime import datetime
import json, csv, os

# Gerekli fonksiyonlar
from api import read_orders, save_orders_to_json
from utils import calc_days_ago, delete_order, add_to_done_orders
from depo import get_depo_urunler

# API çekme fonksiyon adayları
_fetch_candidates = []
_merge_candidate = None
try:
    from api import entegrabilisim_get_all_orders
    _fetch_candidates.append(entegrabilisim_get_all_orders)
except: pass
try:
    from api import get_all_orders
    _fetch_candidates.append(get_all_orders)
except: pass
try:
    from api import fetch_orders_from_api
    _fetch_candidates.append(fetch_orders_from_api)
except: pass
try:
    from api import merge_and_save_orders
    _merge_candidate = merge_and_save_orders
except: pass

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

OUTPUT_JSON = "output.json"
LOCATIONS_CSV = "locations.csv"
TOKEN_PATH = "token.txt"

# ---------------- Yardımcılar ----------------
def _load_orders() -> List[Dict[str, Any]]:
    try:
        return read_orders()
    except TypeError:
        return read_orders(OUTPUT_JSON)

def _save_orders(orders: List[Dict[str, Any]]):
    try:
        save_orders_to_json(orders)
    except TypeError:
        save_orders_to_json(orders, OUTPUT_JSON)

def _color_for_order(order: Dict[str, Any]) -> str:
    try:
        dt = datetime.strptime(order.get("datetime", ""), "%Y-%m-%d %H:%M:%S")
        hours = (datetime.now() - dt).total_seconds() / 3600
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

def _enrich_order(o: Dict[str, Any]) -> Dict[str, Any]:
    o = dict(o)
    o["_color"] = _color_for_order(o)
    o["_days_ago"] = calc_days_ago(o.get("datetime", ""))
    return o

def _toggle_collected_by_barcode(barcode: str, value: bool) -> bool:
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

def _read_locations() -> Dict[str, str]:
    if not os.path.exists(LOCATIONS_CSV):
        return {}
    out = {}
    with open(LOCATIONS_CSV, "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                out[row[0]] = row[1]
    return out

def _write_locations(d: Dict[str, str]):
    with open(LOCATIONS_CSV, "w", encoding="utf-8") as f:
        w = csv.writer(f)
        for k, v in sorted(d.items()):
            w.writerow([k, v])

# ---------------- Sayfalar ----------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request,
                durum: str = "TÜMÜ",
                platform: str = "TÜMÜ",
                kargo: str = "TÜMÜ",
                t1: str = "",
                t2: str = ""):
    orders = _load_orders()
    if durum == "TÜMÜ":
        orders = [o for o in orders if "iptal" not in o.get("store_order_status_name", "").lower()]
    # diğer filtreler
    if platform != "TÜMÜ":
        orders = [o for o in orders if o.get("entegration", "") == platform]
    if kargo != "TÜMÜ":
        orders = [o for o in orders if o.get("cargo_company", "") == kargo]
    if t1:
        d1 = datetime.strptime(t1, "%d.%m.%Y")
        orders = [o for o in orders if datetime.strptime(o.get("datetime", ""), "%Y-%m-%d %H:%M:%S") >= d1]
    if t2:
        d2 = datetime.strptime(t2, "%d.%m.%Y")
        orders = [o for o in orders if datetime.strptime(o.get("datetime", ""), "%Y-%m-%d %H:%M:%S") <= d2]

    platformlar = sorted({o.get("entegration", "") for o in _load_orders() if o.get("entegration", "")})
    kargolar = sorted({o.get("cargo_company", "") for o in _load_orders() if o.get("cargo_company", "")})
    return templates.TemplateResponse("index.html", {
        "request": request,
        "orders": [_enrich_order(o) for o in orders],
        "platformlar": platformlar,
        "kargolar": kargolar,
        "durum": durum, "platform": platform, "kargo": kargo,
        "t1": t1, "t2": t2
    })

@app.get("/order/{order_no}", response_class=HTMLResponse)
async def order_detail(request: Request, order_no: str):
    orders = _load_orders()
    order = next((o for o in orders if str(o.get("no")) == str(order_no)), None)
    if not order:
        return PlainTextResponse("Not Found", status_code=404)
    return templates.TemplateResponse("depo.html", {"request": request, "order": _enrich_order(order)})

# ---------------- Toplandı Toggle ----------------
@app.post("/toggle-collected")
async def toggle_collected(request: Request):
    form = await request.form()
    barcode = form.get("barcode")
    value = form.get("value")
    value = str(value).lower() in ("true", "1", "on", "yes")
    _toggle_collected_by_barcode(barcode, value)
    return Response(status_code=204)

@app.post("/picklist/toggle")
async def picklist_toggle(request: Request):
    return await toggle_collected(request)

# ---------------- Onayla + Yazdır ----------------
@app.post("/order/{order_no}/print")
async def order_print(order_no: str):
    try:
        delete_order(order_no)
        add_to_done_orders(order_no)
    except:
        pass
    return RedirectResponse(url="/", status_code=303)

# ---------------- Picklist ----------------
@app.get("/picklist", response_class=HTMLResponse)
async def picklist(request: Request, platform: str = "TÜMÜ", t1: str = "", t2: str = "", q: str = ""):
    d1 = datetime.strptime(t1, "%d.%m.%Y") if t1 else None
    d2 = datetime.strptime(t2, "%d.%m.%Y") if t2 else None
    urunler = get_depo_urunler(_load_orders(), platform, d1, d2, q)
    locs = _read_locations()
    for u in urunler:
        u["depo_yeri"] = locs.get(u["name"], "")
        all_collected = all(pr.get("collected", False) for (_o, pr) in u.get("orders", []))
        u["_collected"] = all_collected
    return templates.TemplateResponse("picklist.html", {
        "request": request, "urunler": urunler,
        "platform": platform, "t1": t1, "t2": t2, "q": q
    })

# ---------------- Depo Yerleri ----------------
@app.get("/locations", response_class=HTMLResponse)
async def locations_page(request: Request, q: str = ""):
    items = [{"name": n, "location": l} for n, l in _read_locations().items()]
    if q:
        ql = q.lower()
        items = [it for it in items if ql in it["name"].lower()]
    return templates.TemplateResponse("locations.html", {"request": request, "items": items, "q": q})

@app.post("/locations/set")
async def locations_set(name: str = Form(...), location: str = Form(...)):
    locs = _read_locations()
    locs[name] = location
    _write_locations(locs)
    return RedirectResponse(url="/locations", status_code=303)

# ---------------- Token ----------------
@app.get("/token", response_class=HTMLResponse)
async def token_form(request: Request):
    cur = ""
    if os.path.exists(TOKEN_PATH):
        cur = open(TOKEN_PATH, "r", encoding="utf-8").read().strip()
    return HTMLResponse(f"""
    <html><body>
    <form method="post" action="/token">
    <input type="text" name="token" value="{cur}">
    <button type="submit">Kaydet</button>
    </form>
    </body></html>
    """)

@app.post("/token")
async def token_save(token: str = Form(...)):
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(token.strip())
    return RedirectResponse(url="/token", status_code=303)

# ---------------- API'den Güncelle ----------------
@app.post("/refresh")
async def refresh_from_api():
    new_orders = []
    for fn in _fetch_candidates:
        try:
            data = fn()
            if isinstance(data, list) and data:
                new_orders = data
                break
        except:
            pass
    if not new_orders:
        return Response(status_code=204)
    if _merge_candidate:
        try:
            _merge_candidate(new_orders, path=OUTPUT_JSON)
            return Response(status_code=204)
        except TypeError:
            _merge_candidate(new_orders)
            return Response(status_code=204)
    cur = _load_orders()
    by_no = {str(o.get("no") or o.get("order_number") or o.get("id")): o for o in cur}
    for n in new_orders:
        key = str(n.get("no") or n.get("order_number") or n.get("id"))
        by_no[key] = n
    _save_orders(list(by_no.values()))
    return Response(status_code=204)
