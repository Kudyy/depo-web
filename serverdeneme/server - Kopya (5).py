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
    tarih = order.get("datetime", "")
    try:
        dt = datetime.strptime(tarih, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        gecen_saat = (now - dt).total_seconds() / 3600
        saat = dt.hour
    except Exception:
        gecen_saat = 0
        saat = 0

    if gecen_saat >= 24:
        return "#c62828"
    elif gecen_saat >= 16:
        return "#f8bb53"
    elif saat < 12:
        return "#f87171"
    else:
        return "#5bc980"

def _enrich_order(o: Dict[str, Any]) -> Dict[str, Any]:
    o = dict(o)
    o["_color"] = _color_for_order(o)
    o["_days_ago"] = calc_days_ago(o.get("datetime", ""))
    return o

def _filter_orders(orders: List[Dict[str, Any]],
                   durum: str, platform: str, kargo: str,
                   t1: Optional[str], t2: Optional[str]) -> List[Dict[str, Any]]:
    res = orders[:]
    if durum == "TÜMÜ":
        res = [o for o in res if "iptal" not in (o.get("store_order_status_name","").lower())]
    else:
        durum_map = {
            "Depodaki Siparişler": ["Depoda", "Depodaki Siparişler"],
            "Devam Eden Siparişler": ["Devam Ediyor", "Hazırlanıyor"],
            "Kargoya Verilecek Siparişler": ["Kargoya Verilecek", "Kargoya Verildi"],
            "Tamamlanan Siparişler": ["Teslim Edildi", "Tamamlandı", "Tamamlanan"],
            "İptal Edilen Siparişler": ["İptal", "İptal Edildi"]
        }
        anahtarlar = [k.lower() for k in durum_map.get(durum, [])]
        if anahtarlar:
            res = [o for o in res if any(k in (o.get("store_order_status_name","").lower()) for k in anahtarlar)]

    if platform and platform != "TÜMÜ":
        res = [o for o in res if o.get("entegration","") == platform]
    if kargo and kargo != "TÜMÜ":
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
async def index(request: Request,
                durum: str = "TÜMÜ",
                platform: str = "TÜMÜ",
                kargo: str = "TÜMÜ",
                t1: str = "",
                t2: str = ""):
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
    cur = None
    for o in orders:
        if str(o.get("no")) == str(order_no) or str(o.get("order_number")) == str(order_no):
            cur = o
            break
    if not cur:
        return HTMLResponse("<h3>404 - Sipariş bulunamadı</h3>", status_code=404)
    cur = _enrich_order(cur)
    return templates.TemplateResponse("depo.html", {"request": request, "order": cur})

@app.post("/order/{order_no}/cancel")
async def order_cancel(order_no: str):
    orders = _load_orders()
    found = False
    for o in orders:
        if str(o.get("no")) == str(order_no) or str(o.get("order_number")) == str(order_no):
            o["store_order_status"] = "-1"
            o["store_order_status_name"] = "İptal Edildi"
            found = True
            break
    if found:
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

# ✅ DÜZELTİLEN KISIM — path parametre + form verisi uyumlu
@app.post("/order/{order_no}/toggle")
async def order_toggle_collected(order_no: str, barcode: str = Form(...), value: Optional[str] = Form(None)):
    v = str(value).lower() in ("true", "1", "on", "yes")
    ok = _toggle_order_line(order_no, barcode, v)
    return PlainTextResponse("OK" if ok else "NO-CHANGE", status_code=200)

# ----------------- Picklist -----------------
@app.get("/picklist", response_class=HTMLResponse)
async def picklist(request: Request,
                   platform: str = "TÜMÜ",
                   t1: str = "",
                   t2: str = "",
                   q: str = ""):
    orders = _load_orders()
    d1 = d2 = None
    try:
        d1 = datetime.strptime(t1.strip(), "%d.%m.%Y") if t1.strip() else None
    except Exception:
        pass
    try:
        d2 = datetime.strptime(t2.strip(), "%d.%m.%Y") if t2.strip() else None
    except Exception:
        pass

    if get_depo_urunler:
        urunler = get_depo_urunler(orders, platform, d1, d2, q.strip())
        for u in urunler:
            all_col = all(urun.get("collected", False) for (_, urun) in u.get("orders", []))
            u["_collected"] = all_col
            u["depo_yeri"] = _get_location_for(u.get("name",""))
    else:
        urunler = []

    return templates.TemplateResponse("picklist.html", {
        "request": request,
        "urunler": urunler,
        "platform": platform,
        "t1": t1,
        "t2": t2,
        "q": q
    })

@app.post("/picklist/toggle")
async def picklist_toggle(barcode: str = Form(...), value: Optional[str] = Form(None)):
    v = str(value).lower() in ("true", "1", "on", "yes")
    ok = _toggle_collected_by_barcode(barcode, v)
    return PlainTextResponse("OK" if ok else "NO-CHANGE", status_code=200)

# ----------------- Depo Yerleri -----------------
def _read_locations() -> Dict[str, str]:
    if not os.path.exists(LOCATIONS_CSV):
        return {}
    out = {}
    with open(LOCATIONS_CSV, "r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        for row in r:
            if len(row) >= 2:
                out[row[0]] = row[1]
    return out

def _write_locations(d: Dict[str, str]):
    with open(LOCATIONS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for k, v in sorted(d.items()):
            w.writerow([k, v])

def _get_location_for(name: str) -> Optional[str]:
    return _read_locations().get(name)

@app.get("/locations", response_class=HTMLResponse)
async def locations_page(request: Request, q: str = ""):
    loc = _read_locations()
    items = [{"name": k, "location": v} for k, v in loc.items()]
    if q.strip():
        ql = q.strip().lower()
        items = [it for it in items if ql in it["name"].lower()]
    items.sort(key=lambda x: x["name"].lower())
    return templates.TemplateResponse("locations.html", {"request": request, "items": items, "q": q})

@app.post("/locations/set")
async def locations_set(name: str = Form(...), location: str = Form(...)):
    loc = _read_locations()
    loc[name] = location
    _write_locations(loc)
    return RedirectResponse(url="/locations", status_code=303)

@app.get("/locations/export")
async def locations_export():
    if not os.path.exists(LOCATIONS_CSV):
        open(LOCATIONS_CSV, "w").close()
    with open(LOCATIONS_CSV, "r", encoding="utf-8") as f:
        content = f.read()
    headers = {"Content-Disposition": "attachment; filename=locations.csv"}
    return PlainTextResponse(content, headers=headers, media_type="text/csv")

@app.post("/locations/import")
async def locations_import(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    rows = [r.split(",") for r in text.splitlines() if r.strip()]
    loc = _read_locations()
    for r in rows:
        if len(r) >= 2:
            loc[r[0].strip()] = r[1].strip()
    _write_locations(loc)
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
    html = f"""
    <!doctype html><html><head><meta charset="utf-8"><title>Token Güncelle</title>
    <link rel="stylesheet" href="/static/styles.css" />
    </head><body class="container">
      <h1>Token Güncelle</h1>
      <form method="post" action="/token">
        <input type="text" name="token" value="{cur}" style="width: 100%;" />
        <button type="submit" class="btn primary" style="margin-top:8px">Kaydet</button>
      </form>
      <p style="margin-top:16px"><a href="/">← Siparişler</a></p>
    </body></html>
    """
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