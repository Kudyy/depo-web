# api.py

import requests
import json
from datetime import datetime, timedelta

JSON_PATH = "output.json"

def get_access_token():
    try:
        with open("token.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except:
        return ""

ACCESS_TOKEN = get_access_token()

def entegrabilisim_get_orders_last_24h(page=1, limit=200):
    url = f"https://apiv2.entegrabilisim.com/order/page={page}/"
    headers = {
        "Authorization": f"JWT {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    now = datetime.now()
    one_day_ago = now - timedelta(hours=18)
    start_date = one_day_ago.strftime('%Y-%m-%d %H:%M:%S')
    end_date = now.strftime('%Y-%m-%d %H:%M:%S')
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("orders", [])
    except Exception as e:
        print(f"API sipariş çekme hatası: {e}")
        return []

def entegrabilisim_get_all_orders():
    all_orders = []
    page = 1
    while True:
        orders = entegrabilisim_get_orders_last_24h(page=page)
        if not orders:
            break
        all_orders.extend(orders)
        if len(orders) < 200:
            break
        page += 1
    return all_orders

def merge_and_save_orders(new_orders, path=JSON_PATH):
    # Önce işlenmiş (done) sipariş no'larını al
    try:
        with open("done_orders.json", "r", encoding="utf-8") as f:
            done_list = set(json.load(f)["orders"])
    except Exception:
        done_list = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            old_data = json.load(f)
            old_orders = old_data.get("orders", [])
    except Exception:
        old_orders = []
    order_ids = {str(o.get("no") or o.get("id")) for o in old_orders}
    # Hem eski hem yeni siparişlerde done_list'te olanları filtrele!
    merged = [
        o for o in (old_orders + [o for o in new_orders if str(o.get("no") or o.get("id")) not in order_ids])
        if str(o.get("no")) not in done_list and str(o.get("order_number")) not in done_list
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"orders": merged}, f, ensure_ascii=False, indent=2)

def save_orders_to_json(orders, path=JSON_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"orders": orders}, f, ensure_ascii=False, indent=2)

def read_orders(path=JSON_PATH):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("orders", [])
    except Exception:
        return []

def archive_old_orders(days=30, path=JSON_PATH, archive_path="archive.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        orders = data.get("orders", [])
    except Exception:
        orders = []
    now = datetime.now()
    keep, archive = [], []
    for o in orders:
        dt = o.get("datetime", "")
        try:
            tarih = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            if o.get("store_order_status") == "4" and (now - tarih).days >= days:
                archive.append(o)
            else:
                keep.append(o)
        except:
            keep.append(o)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"orders": keep}, f, ensure_ascii=False, indent=2)
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump({"orders": archive}, f, ensure_ascii=False, indent=2)
