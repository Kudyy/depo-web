#!/usr/bin/env python3
"""
Railway deployment script for Depo Web Application
"""
import os
import sys

def main():
    # Get port from Railway environment
    port = os.environ.get("PORT", "8000")
    host = os.environ.get("HOST", "0.0.0.0")
    
    print(f"🚀 Starting Depo Web Application on {host}:{port}")
    
    # Import and run uvicorn
    try:
        import uvicorn
        from server import app
        
        uvicorn.run(
            app,
            host=host,
            port=int(port),
            log_level="info",
            access_log=True
        )
    except ImportError as e:
        print(f"❌ Import error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

import tkinter as tk
from tkinter import ttk, messagebox
from api import read_orders, save_orders_to_json, entegrabilisim_get_all_orders, merge_and_save_orders
from utils import unique_list, calc_days_ago, get_hour, delete_order, add_to_done_orders
from invoice import print_invoice_direct
from datetime import datetime

root = tk.Tk()
root.title("Sipariş Takip Sistemi")
root.geometry("1500x830")
root.config(bg="#e7eaff")

toplam_siparis_var = tk.StringVar(value="Toplam Sipariş: 0")

filter_frame = tk.Frame(root, background="#e7eaff")
filter_frame.pack(side=tk.TOP, fill=tk.X, padx=14, pady=6)

durumlar = [
    "TÜMÜ", "Depodaki Siparişler", "Devam Eden Siparişler", "Kargoya Verilecek Siparişler",
    "Tamamlanan Siparişler", "İptal Edilen Siparişler"
]
durum_var = tk.StringVar(value="TÜMÜ")
platform_var = tk.StringVar(value="TÜMÜ")
kargo_var = tk.StringVar(value="TÜMÜ")
tarih1_var = tk.StringVar()
tarih2_var = tk.StringVar()

filter_inner = tk.Frame(filter_frame, background="#e7eaff")
filter_inner.pack(side="left", fill="x", expand=True)

tk.Label(filter_inner, text="Durum:", background="#e7eaff", font=("Arial", 12, "bold")).pack(side="left", padx=(0,2))
ttk.Combobox(filter_inner, values=durumlar, textvariable=durum_var, width=20, state="readonly").pack(side="left", padx=(0,8))

tk.Label(filter_inner, text="Platform:", background="#e7eaff", font=("Arial", 12, "bold")).pack(side="left", padx=(0,2))
platformlar = unique_list([str(o.get("entegration","")) for o in read_orders() if o.get("entegration","")])
ttk.Combobox(filter_inner, values=["TÜMÜ"] + platformlar, textvariable=platform_var, width=14, state="readonly").pack(side="left", padx=(0,8))

tk.Label(filter_inner, text="Kargo:", background="#e7eaff", font=("Arial", 12, "bold")).pack(side="left", padx=(0,2))
kargolar = unique_list([str(o.get("cargo_company","")) for o in read_orders() if o.get("cargo_company","")])
ttk.Combobox(filter_inner, values=["TÜMÜ"] + kargolar, textvariable=kargo_var, width=14, state="readonly").pack(side="left", padx=(0,8))

tk.Label(filter_inner, text="Tarih (GG.AA.YYYY):", background="#e7eaff", font=("Arial", 12, "bold")).pack(side="left", padx=(0,2))
tk.Entry(filter_inner, textvariable=tarih1_var, width=12, font=("Arial",11)).pack(side="left", padx=(0,1))
tk.Label(filter_inner, text="-", background="#e7eaff", font=("Arial",11)).pack(side="left")
tk.Entry(filter_inner, textvariable=tarih2_var, width=12, font=("Arial",11)).pack(side="left", padx=(0,10))

def filtre_ve_ara():
    refresh_cards()
tk.Button(filter_inner, text="Ara", command=filtre_ve_ara, font=("Arial", 11, "bold"), background="#e3f0ff", foreground="#19456b", bd=0, padx=8, pady=2, activebackground="#b8e2f2", width=7).pack(side="left", padx=(2,2))

def depo_urun_set_collected(barcode, value):
    orders = read_orders()
    for order in orders:
        for urun in order.get("order_product", []):
            if urun.get("barcode", "") == barcode:
                urun["collected"] = value
    save_orders_to_json(orders)

def ac_depo_penceresi():
    from depo import DepoPencere, get_depo_urunler
    DepoPencere(root, depo_urun_set_collected, get_depo_urunler)

def token_guncelle_popup():
    win = tk.Toplevel()
    win.title("Token Güncelle")
    ent = tk.Entry(win, width=50)
    ent.pack(pady=5)
    try:
        with open("token.txt", "r", encoding="utf-8") as f:
            ent.insert(0, f.read().strip())
    except:
        pass
    def kaydet():
        with open("token.txt", "w", encoding="utf-8") as f:
            f.write(ent.get())
        messagebox.showinfo("Başarılı", "Token güncellendi. Uygulamayı yeniden başlatın.")
        win.destroy()
    tk.Button(win, text="Kaydet", command=kaydet, font=("Arial",11)).pack(pady=5)

button_main_style = {"font": ("Arial", 11, "bold"), "bd":0, "padx":8, "pady":2}
button_token_style = {"font": ("Arial", 9, "bold"), "bg":"#e6e6e6", "fg":"#1a1a1a", "bd":0, "relief":"ridge"}
btnbar = tk.Frame(filter_frame, background="#e7eaff")
btnbar.pack(side="right", padx=(0,0))
tk.Button(btnbar, text="Depodan Toplanacaklar", command=ac_depo_penceresi,
          background="#bde6ff", foreground="#153d6f", **button_main_style, width=20).pack(side="top", pady=(3,2))
tk.Button(btnbar, text="Yenile (API'dan Çek)", command=lambda: yenile_orders_api(),
          background="#fff6c6", foreground="#856404", **button_main_style, width=20).pack(side="top", pady=(3,2))
tk.Button(btnbar, text="⚙️", command=token_guncelle_popup, **button_token_style, width=3, height=1).pack(side="top", pady=(8,1))

canvas_frame = tk.Frame(root, background="#e7eaff")
canvas_frame.pack(fill="both", expand=True, padx=18, pady=8)
canvas = tk.Canvas(canvas_frame, background="#e7eaff", highlightthickness=0)
scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)
siparisler_frame = tk.Frame(canvas, background="#e7eaff")
canvas.create_window((0, 0), window=siparisler_frame, anchor='nw')

def on_configure(event):
    canvas.configure(scrollregion=canvas.bbox('all'))
siparisler_frame.bind("<Configure>", on_configure)
def _on_mousewheel(event):
    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

toplam_label_frame = tk.Frame(root, background="#e7eaff")
toplam_label_frame.pack(side="bottom", fill="x")
toplam_label = tk.Label(toplam_label_frame, textvariable=toplam_siparis_var, font=("Arial", 14, "bold"), background="#e7eaff", foreground="#273144", anchor="w")
toplam_label.pack(side="left", padx=16, pady=(4,7))

def show_order_popup(order):
    popup = tk.Toplevel(root)
    popup.title("Sipariş Detayı")
    popup.geometry("660x420")
    popup.config(bg="#f5f6fa")
    tarih = order.get("datetime", "")
    try:
        dt = datetime.strptime(tarih, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        gecen_saat = (now - dt).total_seconds() / 3600
        saat = dt.hour
    except:
        gecen_saat = 0
        saat = 0
    if gecen_saat >= 24:
        header_bg = "#c62828"
    elif gecen_saat >= 16:
        header_bg = "#f8bb53"
    elif saat < 12:
        header_bg = "#f87171"
    else:
        header_bg = "#5bc980"
    header = tk.Frame(popup, background=header_bg)
    header.pack(fill="x", padx=0, pady=0)
    musteri = f"{order.get('firstname','')} {order.get('lastname','')}".strip()
    tk.Label(header, text=musteri, font=("Arial", 16, "bold"), background=header_bg, foreground="white").pack(side="left", padx=14, pady=10)
    tk.Label(header, text=f"Order ID: {order.get('no','')}", font=("Arial", 12, "bold"), background=header_bg, foreground="white").pack(side="right", padx=14)
    info = tk.Frame(popup, background="#f5f6fa")
    info.pack(fill="x", pady=(6,2))
    tk.Label(info, text=f"Tarih: {order.get('datetime','')}", font=("Arial", 11), background="#f5f6fa").pack(side="left", padx=10)
    tk.Label(info, text=f"Toplam: {order.get('grand_total','')} TL", font=("Arial", 11), background="#f5f6fa").pack(side="left", padx=16)
    tk.Label(info, text=f"Platform: {order.get('entegration','')}", font=("Arial", 11), background="#f5f6fa").pack(side="left", padx=16)
    tk.Label(info, text=f"Kargo: {order.get('cargo_company','')}", font=("Arial", 11), background="#f5f6fa").pack(side="left", padx=16)
    adres = order.get("ship_address") or order.get("invoice_address") or ""
    tk.Label(popup, text=f"Adres: {adres}", font=("Arial", 10), background="#f5f6fa", anchor="w", wraplength=580, justify="left").pack(fill="x", padx=18, pady=5)
    urunler = order.get("order_product", [])
    urunler_box = tk.Frame(popup, background="#ebf2fa", bd=2, relief="ridge")
    urunler_box.pack(fill="x", padx=16, pady=(10,3))
    tk.Label(urunler_box, text="Ürünler", font=("Arial", 11, "bold"), background="#ebf2fa").grid(row=0, column=0, padx=8, pady=(3,1), sticky="w")
    headers = ["Ürün İsmi", "Barkod", "Adet", "Fiyat", "Toplandı mı?"]
    for j, h in enumerate(headers):
        tk.Label(urunler_box, text=h, font=("Arial", 9, "bold"), background="#ebf2fa").grid(row=1, column=j, padx=3, sticky="w")
    urun_vars = []
    for i, urun in enumerate(urunler):
        tk.Label(urunler_box, text=urun.get("name", ""), background="#ebf2fa", wraplength=170, anchor="w").grid(row=i+2, column=0, sticky="w", padx=3)
        tk.Label(urunler_box, text=urun.get("barcode", ""), background="#ebf2fa").grid(row=i+2, column=1)
        tk.Label(urunler_box, text=urun.get("quantity", ""), background="#ebf2fa").grid(row=i+2, column=2)
        tk.Label(urunler_box, text=urun.get("price", ""), background="#ebf2fa").grid(row=i+2, column=3)
        var = tk.BooleanVar(value=urun.get("collected", False))
        def cb_update(barcode=urun.get("barcode"), v=var):
            orders = read_orders()
            for order_x in orders:
                for urun_x in order_x.get("order_product", []):
                    if urun_x.get("barcode", "") == barcode:
                        urun_x["collected"] = v.get()
            save_orders_to_json(orders)
        cb = tk.Checkbutton(urunler_box, variable=var, background="#ebf2fa", command=cb_update)
        cb.grid(row=i+2, column=4)
        urun_vars.append(var)
    btn_frame = tk.Frame(popup, background="#f5f6fa")
    btn_frame.pack(pady=12)
    def iptal_et(order):
        orders = read_orders()
        for o in orders:
            if str(o.get("no")) == str(order.get("no")):
                o["store_order_status"] = "-1"
                o["store_order_status_name"] = "İptal Edildi"
        save_orders_to_json(orders)
        refresh_cards()
        popup.destroy()
    def try_print_invoice():
        if all(v.get() for v in urun_vars):
            try:
                # YAZICIYA OTOMATİK GÖNDER (EKRAN GELMEDEN)
                print_invoice_direct(order)
                # Burada istersek siparişi silip done_orders’a da ekleyebiliriz
                delete_order(order.get("no"))
                add_to_done_orders(order.get("no"))
            except Exception as e:
                messagebox.showerror("Hata", f"Yazdırma sırasında hata oluştu:\n{e}")
            finally:
                popup.destroy()
                refresh_cards()
        else:
            messagebox.showwarning("Eksik", "Tüm ürünleri toplamalısınız.")
    tk.Button(btn_frame, text="Onayla ve Faturayı Yazdır", font=("Arial",11,"bold"), background="#4ad29a", foreground="#fff", command=try_print_invoice).pack(side="left", padx=8)
    tk.Button(btn_frame, text="İptal Et", font=("Arial",10), background="#fff", foreground="#c62828", command=lambda: iptal_et(order)).pack(side="left", padx=8)

def refresh_cards():
    for widget in siparisler_frame.winfo_children():
        widget.destroy()

    orders = read_orders()
    f_durum = durum_var.get()

    def is_iptal(o):
        status_name = (o.get("store_order_status_name") or "").lower()
        status = str(o.get("store_order_status", "")).strip()
        return ("iptal" in status_name) or (status == "-1")

    if f_durum == "TÜMÜ":
        orders = [o for o in orders if not is_iptal(o)]
    elif f_durum == "İptal Edilen Siparişler":
        orders = [o for o in orders if is_iptal(o)]
    else:
        durum_map = {
            "Depodaki Siparişler": ["Depoda", "Depodaki Siparişler"],
            "Devam Eden Siparişler": ["Devam Ediyor", "Hazırlanıyor"],
            "Kargoya Verilecek Siparişler": ["Kargoya Verilecek", "Kargoya Verildi"],
            "Tamamlanan Siparişler": ["Teslim Edildi", "Tamamlandı", "Tamamlanan"]
        }
        keywords = durum_map.get(f_durum, [])
        orders = [
            o for o in orders
            if any(k.lower() in (o.get("store_order_status_name") or "").lower() for k in keywords)
            and not is_iptal(o)
        ]

    if platform_var.get() != "TÜMÜ":
        orders = [o for o in orders if o.get("entegration", "") == platform_var.get()]
    if kargo_var.get() != "TÜMÜ":
        orders = [o for o in orders if o.get("cargo_company", "") == kargo_var.get()]
    t1 = tarih1_var.get().strip()
    t2 = tarih2_var.get().strip()
    d1 = datetime.strptime(t1, "%d.%m.%Y") if t1 else None
    d2 = datetime.strptime(t2, "%d.%m.%Y") if t2 else None
    if d1:
        orders = [o for o in orders if datetime.strptime(o.get("datetime", ""), "%Y-%m-%d %H:%M:%S") >= d1]
    if d2:
        orders = [o for o in orders if datetime.strptime(o.get("datetime", ""), "%Y-%m-%d %H:%M:%S") <= d2]

    # Sadece ürünlerinin herhangi biri toplanmış olan siparişler
    orders = [
        o for o in orders
        if any(u.get("collected", False) for u in o.get("order_product", []))
    ]

    # Siparişleri sipariş no’suna göre tekilleştir
    seen = set()
    unique_orders = []
    for o in orders:
        no = str(o.get("no"))
        if no not in seen:
            unique_orders.append(o)
            seen.add(no)
    orders = unique_orders

    toplam_siparis_var.set(f"Toplam Sipariş: {len(orders)}")

    for idx, order in enumerate(orders):
        card = tk.Frame(siparisler_frame, background="#273144", height=105, width=1230, bd=0, relief="ridge")
        card.pack(fill="x", pady=(0,12), padx=5)
        card.grid_propagate(False)
        tarih = order.get("datetime", "")
        try:
            dt = datetime.strptime(tarih, "%Y-%m-%d %H:%M:%S")
            saat = dt.hour
            now = datetime.now()
            gecen_saat = (now - dt).total_seconds() / 3600
            gun_once = calc_days_ago(tarih)
        except:
            gecen_saat = 0
            saat = 0
            gun_once = ""
        if gecen_saat >= 24:
            renk = "#c62828"
        elif gecen_saat >= 16:
            renk = "#f8bb53"
        elif saat < 12:
            renk = "#f87171"
        else:
            renk = "#5bc980"

        gradient = tk.Canvas(card, width=100, height=105, background="#ffb0b0", highlightthickness=0)
        gradient.place(x=0, y=0)
        gradient.create_oval(-60, 20, 90, 130, fill=renk, outline=renk)
        gradient.create_rectangle(45, 0, 145, 120, fill="#273144", outline="#273144")
        gradient.create_text(34, 60, text="❗", font=("Arial", 36, "bold"), fill="#fff")
        musteri = f"{order.get('firstname','')} {order.get('lastname','')}".strip()
        order_id = order.get("no", "")
        toplam = order.get("grand_total", "")
        urunler = order.get("order_product", [])
        toplam_urun = len(urunler)
        toplanan_urun = sum(1 for u in urunler if u.get("collected", False))
        eslesen_urun = sum(1 for u in urunler if u.get("collected", False))
        tk.Label(card, text=musteri, font=("Arial", 15, "bold"), background="#273144", foreground="#fff").place(x=105, y=10)
        tk.Label(card, text=f"Order Id: {order_id}", font=("Arial", 11, "bold"), background="#273144", foreground="#f7e7b8").place(x=600, y=13)
        tk.Label(card, text=f"Toplam: {toplam} TL", font=("Arial", 11, "bold"), background="#273144", foreground="#f7e7b8").place(x=900, y=13)
        tk.Label(card, text=f"{tarih[:16]}", font=("Arial", 11), background="#273144", foreground="#fff").place(x=105, y=35)
        orta_y = 55
        tk.Label(card, text=f"Depodan Çıkan Ürün", font=("Arial",10), background="#273144", foreground="#e6e6e6").place(x=230, y=orta_y)
        tk.Label(card, text=str(toplanan_urun), font=("Arial",13,"bold"), background="#273144", foreground="#fff").place(x=390, y=orta_y)
        tk.Label(card, text=f"Eşleşen Ürün", font=("Arial",10), background="#273144", foreground="#e6e6e6").place(x=460, y=orta_y)
        tk.Label(card, text=str(eslesen_urun), font=("Arial",13,"bold"), background="#273144", foreground="#4ad29a").place(x=610, y=orta_y)
        tk.Label(card, text=f"Toplam Ürün", font=("Arial",10), background="#273144", foreground="#e6e6e6").place(x=670, y=orta_y)
        tk.Label(card, text=str(toplam_urun), font=("Arial",13,"bold"), background="#273144", foreground="#fff").place(x=810, y=orta_y)
        platform = order.get("entegration","")
        kargo = order.get("cargo_company","")
        tk.Label(card, text=platform, font=("Arial",13,"bold"), background="#fff", foreground="#c62828", bd=0, relief="flat").place(x=960, y=63, width=144, height=36)
        tk.Label(card, text=f"{gun_once}", font=("Arial",10,"bold"), background="#273144", foreground="#ff5050").place(x=1120, y=77)
        tk.Label(card, text=kargo, font=("Arial",10,"bold"), background="#273144", foreground="#f7e7b8").place(x=960, y=40)
        card.bind("<Button-1>", lambda e, o=order: show_order_popup(o))
        for w in card.winfo_children():
            w.bind("<Button-1>", lambda e, o=order: show_order_popup(o))
        gradient.bind("<Button-1>", lambda e, o=order: show_order_popup(o))

def yenile_orders_api():
    def run():
        new_orders = entegrabilisim_get_all_orders()
        if new_orders:
            merge_and_save_orders(new_orders)
            refresh_cards()
            messagebox.showinfo("Başarılı", "Son 24 saatlik siparişler güncellendi!")
        else:
            messagebox.showwarning("Uyarı", "API'dan yeni sipariş çekilemedi!")
    import threading
    threading.Thread(target=run).start()

def auto_update_orders():
    yenile_orders_api()
    root.after(30*60*1000, auto_update_orders)

refresh_cards()
root.after(10*1000, auto_update_orders)
root.mainloop()
