from datetime import datetime
import json
import os

def calc_days_ago(order_date):
    try:
        sip_tarih = datetime.strptime(order_date, "%Y-%m-%d %H:%M:%S")
        bugun = datetime.now()
        fark = (bugun - sip_tarih).days
        return f"-{fark} gün"
    except:
        return ""

def get_hour(order_date):
    try:
        sip_tarih = datetime.strptime(order_date, "%Y-%m-%d %H:%M:%S")
        return sip_tarih.hour
    except:
        return 0

def unique_list(lst):
    return sorted(list({x for x in lst if x and x.strip()}))


def delete_order(order_no):
    out_file = "output.json"
    with open(out_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    kalanlar = []
    silinen = None
    for sip in data["orders"]:
        # Sipariş no'yu hem "no" hem "order_number" alanında kontrol et
        if (
            str(sip.get("no")) == str(order_no)
            or str(sip.get("order_number")) == str(order_no)
        ):
            silinen = sip
        else:
            kalanlar.append(sip)
    # Yalnızca bulduysan güncelle!
    if silinen:
        data["orders"] = kalanlar
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Sipariş {order_no} silindi.")
    else:
        print("Sipariş bulunamadı, hiçbir şey silinmedi!")

def add_to_done_orders(order_no):
    file = 'done_orders.json'
    try:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"orders": []}
    if str(order_no) not in data["orders"]:
        data["orders"].append(str(order_no))
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)



