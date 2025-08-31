import tkinter as tk
from tkinter import ttk
from api import read_orders
from utils import unique_list, calc_days_ago
import requests
import io
from PIL import Image, ImageTk
from datetime import datetime

IMG_CACHE = {}

def normalize_platform(plat):
    plat = (plat or "").strip().lower()
    if "trendyol" in plat:
        return "trendyol"
    if "hepsiburada" in plat:
        return "hepsiburada"
    if "amazon" in plat:
        return "amazon"
    if "n11" in plat:
        return "n11"
    if "ciceksepeti" in plat:
        return "ciceksepeti"
    if "pazarama" in plat:
        return "pazarama"
    if "idefix" in plat:
        return "idefix"
    return plat

def get_depo_urunler(siparisler, platform_filter=None, date_start=None, date_end=None, arama_terimi=None):
    gruplu = {}
    for order in siparisler:
        durum = (order.get("store_order_status_name", "") or "").lower()
        kargoya_verildi_kelimeleri = [
            "tamamlandı", "teslim edildi", "iptal", "iptal edildi"
        ]
        if any(anahtar in durum for anahtar in kargoya_verildi_kelimeleri):
            continue
        if platform_filter and platform_filter.strip().upper() != "TÜMÜ":
            order_platform = normalize_platform(order.get("entegration", "")).upper()
            if order_platform != platform_filter.strip().upper():
                continue
        tarih = order.get("datetime", "")
        try:
            order_dt = datetime.strptime(tarih, "%Y-%m-%d %H:%M:%S")
            if date_start and order_dt < date_start:
                continue
            if date_end and order_dt > date_end:
                continue
        except:
            pass
        for urun in order.get("order_product", []):
            key = (urun.get("name", ""), urun.get("barcode", ""))
            if key not in gruplu:
                gruplu[key] = {
                    "name": urun.get("name", ""),
                    "barcode": urun.get("barcode", ""),
                    "stock_code": urun.get("store_stock_code", ""),
                    "picture": urun.get("picture", ""),
                    "adet": 0,
                    "days_ago": calc_days_ago(tarih),
                    "orders": [],
                    "platformlar": {},
                }
            gruplu[key]["adet"] += int(urun.get("quantity", 1))
            gruplu[key]["orders"].append((order, urun))
            if gruplu[key]["days_ago"] > calc_days_ago(tarih):
                gruplu[key]["days_ago"] = calc_days_ago(tarih)
            platform = normalize_platform(order.get("entegration", "")).upper()
            siparis_no = order.get("order_number", order.get("order_no", order.get("id", "")))
            if platform:
                if platform not in gruplu[key]["platformlar"]:
                    gruplu[key]["platformlar"][platform] = []
                gruplu[key]["platformlar"][platform].append({
                    "adet": int(urun.get("quantity", 1)),
                    "siparis_no": siparis_no
                })
    urunler = list(gruplu.values())
    urunler.sort(key=lambda u: u.get("name", "").lower())
    if arama_terimi:
        at = arama_terimi.lower()
        def match(u):
            return (
                at in (u["name"] or "").lower()
                or at in (u["barcode"] or "").lower()
                or at in (u["stock_code"] or "").lower()
            )
        urunler = [u for u in urunler if match(u)]
    return urunler

def kisa_ad(ad, maxlen=46):
    return ad[:maxlen] + "..." if len(ad) > maxlen else ad

class DepoPencere(tk.Toplevel):
    def __init__(self, ana_root, set_collected_func, get_depo_urunler_func):
        super().__init__(ana_root)
        self.set_collected_func = set_collected_func
        self.get_depo_urunler = get_depo_urunler_func

        self.title("Depodan Toplanacaklar")
        self.geometry("1350x900")
        self.config(bg="#F3F4F6")
        self.resizable(True, True)
        self.urun_gorseller = {}

        tum_platformlar = [normalize_platform(o.get("entegration","")).upper() for o in read_orders() if o.get("entegration","")]
        platformlar = ["TÜMÜ"] + sorted(list({p for p in tum_platformlar if p}))
        self.platform_var = tk.StringVar(value="TÜMÜ")
        self.tarih1 = tk.StringVar()
        self.tarih2 = tk.StringVar()
        self.search_var = tk.StringVar()

        # Üst filtre barı
        filtre_frame = tk.Frame(self, bg="#e0eaff", bd=0)
        filtre_frame.pack(fill="x", padx=12, pady=(12, 7))
        ttk.Label(filtre_frame, text="Platform:", background="#e0eaff", font=("Arial", 13, "bold")).pack(side="left", padx=(6,2))
        self.cmb_platform = ttk.Combobox(filtre_frame, values=platformlar, textvariable=self.platform_var, width=16, state="readonly", font=("Arial", 12))
        self.cmb_platform.pack(side="left", padx=4, ipady=3)
        ttk.Label(filtre_frame, text="Tarih Aralığı:", background="#e0eaff", font=("Arial", 13, "bold")).pack(side="left", padx=9)
        tk.Entry(filtre_frame, textvariable=self.tarih1, width=12, font=("Arial", 12)).pack(side="left", padx=(0,2))
        ttk.Label(filtre_frame, text="-", background="#e0eaff", font=("Arial", 13, "bold")).pack(side="left")
        tk.Entry(filtre_frame, textvariable=self.tarih2, width=12, font=("Arial", 12)).pack(side="left", padx=(2,2))
        tk.Button(filtre_frame, text="Uygula", command=self.guncelle, bg="#2563eb", fg="#fff", font=("Arial", 12, "bold"), relief="flat", padx=14, pady=2).pack(side="left", padx=9)

        # Arama barı
        search_frame = tk.Frame(self, bg="#e0eaff")
        search_frame.pack(fill="x", padx=12, pady=(0,9))
        tk.Label(search_frame, text="Ürün adı / Stok kodu / Barkod ile ara:", bg="#e0eaff", font=("Arial", 12)).pack(side="left", padx=7)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=28, font=("Arial", 12))
        search_entry.pack(side="left", padx=(2,2))
        tk.Button(search_frame, text="Ara", command=self.guncelle, bg="#0ea5e9", fg="#fff", font=("Arial", 11, "bold"), relief="flat", padx=7).pack(side="left", padx=7)
        search_entry.bind("<Return>", lambda e: self.guncelle())

        # Canvas+Frame+Scroll
        self.canvas = tk.Canvas(self, bg="#F3F4F6", borderwidth=0, highlightthickness=0)
        self.urun_frame = tk.Frame(self.canvas, bg="#F3F4F6")
        self.scrollbar_y = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar_y.set)
        self.scrollbar_y.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.create_window((0,0), window=self.urun_frame, anchor='nw')

        def on_frame_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.urun_frame.bind("<Configure>", on_frame_configure)

        # HER YERDE SCROLL ÇALIŞSIN!
        self.bind("<Enter>", lambda e: self._activate_mousewheel())
        self.bind("<Leave>", lambda e: self._deactivate_mousewheel())

        self.guncelle()

    def _activate_mousewheel(self):
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _deactivate_mousewheel(self):
        self.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def get_img(self, url):
        if not url:
            url = "https://cdn-icons-png.flaticon.com/512/10148/10148616.png"
        if url in IMG_CACHE:
            return IMG_CACHE[url]
        try:
            resp = requests.get(url, timeout=3)
            im = Image.open(io.BytesIO(resp.content))
            im.thumbnail((170,170))
            photo = ImageTk.PhotoImage(im)
            IMG_CACHE[url] = photo
            return photo
        except:
            resp = requests.get("https://cdn-icons-png.flaticon.com/512/10148/10148616.png")
            im = Image.open(io.BytesIO(resp.content))
            im.thumbnail((150,150))
            photo = ImageTk.PhotoImage(im)
            IMG_CACHE[url] = photo
            return photo

    def urun_platform_popup(self, urun):
        popup = tk.Toplevel(self)
        popup.title("Platformlara Göre Sipariş Dağılımı")
        popup.geometry("400x320")
        popup.config(bg="#f9fafb")
        tk.Label(popup, text=f"{urun['name']}\n({urun['barcode']})", font=("Arial", 12, "bold"), bg="#f9fafb").pack(pady=8)
        frame = tk.Frame(popup, bg="#f9fafb")
        frame.pack(pady=5, padx=12, fill="both", expand=True)
        if urun.get("platformlar"):
            for plat, siplist in urun["platformlar"].items():
                plat_label = tk.Label(frame, text=f"{plat}", font=("Arial", 10, "bold"), bg="#f9fafb", fg="#2563eb")
                plat_label.pack(anchor="w", pady=(10,0))
                for s in siplist:
                    tk.Label(frame, text=f"- {s['adet']} adet | Sipariş No: {s['siparis_no']}", anchor="w", justify="left", bg="#f9fafb").pack(anchor="w", padx=16)
        else:
            tk.Label(frame, text="Hiçbir platformda bulunamadı!", bg="#f9fafb").pack()
        tk.Button(popup, text="Kapat", command=popup.destroy, bg="#e11d48", fg="#fff", font=("Arial", 11, "bold")).pack(pady=10)

    def guncelle(self):
        for w in self.urun_frame.winfo_children():
            w.destroy()
        t1 = self.tarih1.get().strip()
        t2 = self.tarih2.get().strip()
        try:
            d1 = datetime.strptime(t1, "%d.%m.%Y") if t1 else None
        except:
            d1 = None
        try:
            d2 = datetime.strptime(t2, "%d.%m.%Y") if t2 else None
        except:
            d2 = None
        platform = self.platform_var.get()
        arama_terimi = self.search_var.get().strip()
        tum_urunler = self.get_depo_urunler(read_orders(), platform, d1, d2, arama_terimi)
        urunler = [u for u in tum_urunler if not self.is_checked(u)]
        self.vars = []
        self.urunler_list = urunler

        for i, u in enumerate(urunler):
            card = tk.Frame(self.urun_frame, bg="#fff", bd=0, highlightbackground="#e0e7ef", highlightthickness=3)
            card.grid(row=i, column=0, sticky="ew", padx=22, pady=18)
            card.grid_propagate(False)
            card.config(width=1000, height=185)
            card.columnconfigure(1, weight=1)
            card.columnconfigure(2, weight=1)
            card.columnconfigure(3, weight=1)

            # Görsel (büyütülmüş)
            img_frame = tk.Frame(card, bg="#E0E7FF", width=170, height=170)
            img_frame.grid(row=0, column=0, rowspan=3, padx=(18,12), pady=(18,12), sticky="w")
            img = self.get_img(u["picture"])
            img_label = tk.Label(img_frame, image=img, bg="#E0E7FF", width=160, height=160, cursor="hand2")
            img_label.image = img
            img_label.pack()
            img_label.bind("<Button-1>", lambda e, urun=u: self.urun_platform_popup(urun))

            # Bilgiler
            name_lbl = tk.Label(card, text=kisa_ad(u.get("name", "")), bg="#fff", fg="#1e293b", font=("Arial", 17, "bold"))
            name_lbl.grid(row=0, column=1, sticky="w", pady=(26,0))
            info_lbl = tk.Label(card, text=f"Stok: {u.get('stock_code', '')}   Barkod: {u.get('barcode', '')}",
                                bg="#fff", fg="#64748b", font=("Arial", 12))
            info_lbl.grid(row=1, column=1, sticky="w", pady=(10,0))

            # Platform badge
            plats = " ".join(list(u["platformlar"].keys()))
            plat_bg = "#e0e7ff"; plat_fg = "#2563eb"
            if "TRENDYOL" in plats:
                plat_bg = "#fde68a"; plat_fg = "#d97706"
            elif "HEPSIBURADA" in plats:
                plat_bg = "#e0e7ff"; plat_fg = "#2563eb"
            elif "AMAZON" in plats:
                plat_bg = "#d1fae5"; plat_fg = "#10b981"
            elif "N11" in plats:
                plat_bg = "#fee2e2"; plat_fg = "#b91c1c"
            plat_lbl = tk.Label(card, text=plats, bg=plat_bg, fg=plat_fg,
                                font=("Arial", 15, "bold"), padx=14, pady=5, bd=0)
            plat_lbl.grid(row=2, column=1, sticky="w", pady=(12,0))

            # Sağ alt köşe: badge ve checkbox
            side_frame = tk.Frame(card, bg="#fff")
            side_frame.grid(row=2, column=2, sticky="se", padx=(0,30), pady=(0,12))
            adet_bg = "#818cf8"
            adet_lbl = tk.Label(side_frame, text=f"{u.get('adet', '')}", bg=adet_bg, fg="#fff", font=("Arial", 11, "bold"),
                                width=2)
            adet_lbl.pack(side="left", padx=(0,5))
            adet_txt = tk.Label(side_frame, text="Adet", bg="#fff", fg=adet_bg, font=("Arial", 10, "bold"))
            adet_txt.pack(side="left", padx=(0,7))
            gun_raw = u.get('days_ago', '')
            gun_color = "#34d399" if "-0" in gun_raw or "0 gün" in gun_raw else "#ef4444"
            gun_lbl = tk.Label(side_frame, text=gun_raw, bg=gun_color, fg="#fff", font=("Arial", 11, "bold"),
                               width=7)
            gun_lbl.pack(side="left", padx=(0,7))

            # SAĞ ORTADA mantıklı boyutta KARE CHECKBOX!
            var = tk.BooleanVar()
            var.set(self.is_checked(u))
            if not var.get():
                var.set(False)
            self.vars.append(var)
            chk = tk.Checkbutton(
                card, variable=var, bg="#fff", bd=0,
                font=("Arial", 18, "bold"),
                selectcolor="#6ee7b7",
                padx=8, pady=8,
                command=lambda u=u, v=var: self.check_and_save(u, v)
            )
            chk.grid(row=0, column=3, rowspan=3, sticky="e", padx=(0,35), pady=(0,0))
            if not var.get():
                chk.deselect()

        toplam_adet = sum(u["adet"] for u in urunler)
        if not hasattr(self, "lbl_toplam"):
            self.lbl_toplam = tk.Label(self, font=("Arial", 16, "bold"), bg="#F3F4F6", fg="#fff")
            self.lbl_toplam.pack(side="bottom", pady=(10,16), anchor="e")
        self.lbl_toplam.config(
            text=f"  Toplam Ürün Adedi: {toplam_adet}  ",
            bg="#f59e42" if toplam_adet > 0 else "#64748b", fg="#fff"
        )

    def is_checked(self, urun):
        for order, urundict in urun["orders"]:
            if not urundict.get("collected", False):
                return False
        return True

    def check_and_save(self, urun, var):
        self.set_collected_func(urun["barcode"], var.get())
        self.guncelle()
