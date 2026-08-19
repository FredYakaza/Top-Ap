# -*- coding: utf-8 -*-
"""
TOP - TOP Əyləncə Mərkəzi (Flet versiyası - Android APK üçün)
Optimallaşdırılmış Deluxe & Premium Dizayn (Mobil uyğun, animasiyalı, Azərbaycan əlifbası dəstəkli)

Lokal test: flet run main.py
APK qurmaq: flet build apk
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
import flet as ft

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "top_data.json")

# ---------------- Premium & Deluxe Rənglər ----------------
BG = "#070b19"          # Dərin qaranlıq göy fon
CARD_BG = "#111827"     # Kartlar üçün şık tünd rəng
CARD_WARN = "#581c87"   # Vaxtı azalanlar üçün bənövşəyi-tünd qırmızı ton
CARD_WARN2 = "#7e22ce"  # Yanıp-sönmə effekti üçün
ACCENT = "#06b6d4"      # Canlı neon mavi (Cyan)
GREEN = "#10b981"       # Uğurlu / Normal vaxt yaşı
ORANGE = "#f59e0b"      # Xəbərdarlıq sarısı
RED = "#f43f5e"         # Təcili qırmızı / Bitmiş vaxt
TEXT = "#f8fafc"        # Əsas mətn rəngi
MUTED = "#94a3b8"       # İkincil mətn rəngi
WHITE = "#ffffff"
GOLD = "#fbbf24"        # Deluxe detallar üçün qızılı ton

def now():
    return datetime.now()

def fmt_time(dt):
    return dt.strftime("%H:%M")

def fmt_remaining(seconds):
    if seconds == float('inf') or seconds is None:
        return "∞"
    if seconds < 0:
        seconds = 0
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

# ---------------- Data qatı ----------------
class Store:
    def __init__(self, page: ft.Page):
        self.page = page
        self.active = []
        self.logs = []
        self.last_reset_date = None

    async def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.active = data.get("active", [])
                self.logs = data.get("logs", [])
                self.last_reset_date = data.get("last_reset_date")
            except Exception:
                pass

    async def save(self):
        data = {
            "active": self.active,
            "logs": self.logs,
            "last_reset_date": self.last_reset_date,
        }
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Yadda saxlama xətası:", e)

    async def add_child(self, name, entry_dt, exit_dt, note):
        child = {
            "id": str(uuid.uuid4()),
            "name": name,
            "entry": entry_dt.isoformat(),
            "exit": exit_dt.isoformat() if exit_dt else None,
            "note": note,
        }
        self.active.append(child)
        await self.save()
        return child

    def remove_active(self, child_id):
        self.active = [c for c in self.active if c["id"] != child_id]

    async def move_to_log(self, child, status="Bitib"):
        self.remove_active(child["id"])
        log_entry = dict(child)
        log_entry["removed_at"] = now().isoformat()
        log_entry["status"] = status
        self.logs.insert(0, log_entry)
        await self.save()

    async def check_daily_reset(self):
        n = now()
        today_5am = n.replace(hour=5, minute=0, second=0, microsecond=0)
        boundary_date = n.date() if n >= today_5am else (n - timedelta(days=1)).date()
        boundary_str = boundary_date.isoformat()
        if self.last_reset_date != boundary_str and n >= today_5am:
            self.logs = []
            self.last_reset_date = boundary_str
            await self.save()


async def main(page: ft.Page):
    page.title = "TOP - TOP Əyləncə Mərkəzi"
    page.bgcolor = BG
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = None
    
    # Mobil üçün tam ekran və responsiv parametrlər
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    store = Store(page)
    await store.load()

    state = {
        "view": "main",         # "main" | "logs"
        "alerted_ids": set(),
        "new_ids": set(),
        "alert_queue": [],
        "alert_open": False,
        "blink_on": False,
    }

    # UI Komponentləri
    list_column = ft.ListView(expand=True, spacing=10, padding=12, auto_scroll=False)
    subtitle_text = ft.Text("Batutda aktiv olan uşaqlar", size=13, color=MUTED, weight=ft.FontWeight.W_500)

    # ---------- Universal Modal Overlay (Şık animasiyalı) ----------
    overlay_container = ft.Container(
        visible=False,
        bgcolor="#000000DD",
        left=0, top=0, right=0, bottom=0,
        padding=15,
        alignment=ft.alignment.center,
        animate_opacity=300,
    )

    def show_modal(inner_content, box_bgcolor=None):
        box = ft.Container(
            content=inner_content,
            bgcolor=box_bgcolor or CARD_BG,
            border_radius=20,
            padding=24,
            width=360,
            shadow=ft.BoxShadow(spread_radius=2, blur_radius=20, color="#00000088"),
            animate_scale=ft.Animation(300, ft.AnimationCurve.EASE_OUT_BACK),
        )
        overlay_container.content = ft.Column(
            [box],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )
        overlay_container.visible = True
        page.update()

    def hide_modal(e=None):
        overlay_container.visible = False
        page.update()

    # ---------- Kart Qurucu (Mobil üçün ölçüləndirilmiş) ----------
    def build_card(c, remaining):
        is_infinite = c.get("exit") is None
        is_warn = not is_infinite and (0 < remaining <= 180)
        bg = CARD_WARN if is_warn else CARD_BG
        if is_warn and state["blink_on"]:
            bg = CARD_WARN2

        if is_infinite:
            timer_color = GOLD
            time_display = "Limitsiz ∞"
        else:
            timer_color = GREEN if remaining > 300 else (ORANGE if remaining > 180 else RED)
            time_display = fmt_remaining(remaining)

        exit_str = fmt_time(datetime.fromisoformat(c['exit'])) if not is_infinite else "Limitsiz"
        info_text = f"Giriş: {fmt_time(datetime.fromisoformat(c['entry']))}  →  Çıxış: {exit_str}"

        left_items = [
            ft.Text(c["name"], size=16, weight=ft.FontWeight.BOLD, color=TEXT, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(info_text, size=11, color=MUTED),
        ]
        if c.get("note"):
            left_items.append(ft.Text(f"📝 {c['note']}", size=11, color=ACCENT, overflow=ft.TextOverflow.ELLIPSIS))

        async def on_extend(e, cid=c["id"]):
            await extend_time(cid, 30)

        async def on_delete(e, cid=c["id"]):
            await manual_remove(cid, page)

        # Mobil ekranda düymələrin sıxışmaması üçün kompakt Row quruluşu
        action_buttons = [
            ft.Container(
                content=ft.ElevatedButton(
                    "+30 dəq", 
                    bgcolor=ACCENT, 
                    color="#070b19",
                    on_click=on_extend, 
                    height=32,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=5)
                ),
                visible=not is_infinite
            ),
            ft.ElevatedButton(
                "Bitir / Sil", 
                height=32, 
                bgcolor="#1e293b",
                color=RED,
                on_click=on_delete,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=5, side=ft.BorderSide(1, RED))
            ),
        ]

        right_items = ft.Column(
            [
                ft.Text(time_display, size=20, weight=ft.FontWeight.BOLD, color=timer_color),
                ft.Row(action_buttons, spacing=6, alignment=ft.MainAxisAlignment.END),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.END,
            spacing=4,
        )

        card = ft.Container(
            content=ft.Row(
                [
                    ft.Column(left_items, expand=True, spacing=2),
                    right_items,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=bg,
            border_radius=16,
            padding=14,
            border=ft.border.all(1, "#1e293b"),
            animate=ft.Animation(350, ft.AnimationCurve.EASE_IN_OUT),
            animate_opacity=300,
            opacity=1,
            shadow=ft.BoxShadow(blur_radius=10, color="#00000044", offset=ft.Offset(0, 4))
        )
        
        if c["id"] in state["new_ids"]:
            card.opacity = 0
            state["new_ids"].discard(c["id"])

            async def fade_in(card=card):
                await asyncio.sleep(0.05)
                card.opacity = 1
                card.update()

            page.run_task(fade_in)

        return card

    # ---------- Əsas Render Funksiyası ----------
    def render():
        list_column.controls.clear()
        n = now()
        
        if state["view"] == "logs":
            subtitle_text.value = "Günün tarixçəsi və bitən seanslar"
            if not store.logs:
                list_column.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text("📜", size=40),
                            ft.Text("Bugün üçün log qeydi yoxdur", color=MUTED, size=14)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=40, alignment=ft.alignment.center
                    )
                )
            for log in store.logs:
                entry_t = fmt_time(datetime.fromisoformat(log["entry"]))
                exit_t = fmt_time(datetime.fromisoformat(log["exit"])) if log.get("exit") else "Limitsiz"
                removed_t = fmt_time(datetime.fromisoformat(log["removed_at"]))
                items = [
                    ft.Text(log["name"], size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text(f"Giriş: {entry_t} | Plan: {exit_t} | Çıxış: {removed_t}", size=11, color=MUTED),
                ]
                if log.get("note"):
                    items.append(ft.Text(f"📝 {log['note']}", size=11, color=ACCENT))
                
                status_color = RED if "bitib" in log.get("status", "").lower() else MUTED
                list_column.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Column(items, expand=True, spacing=2),
                                ft.Text(log.get("status", "Bitib"), size=11, weight=ft.FontWeight.BOLD, color=status_color),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        bgcolor=CARD_BG, border_radius=14, padding=14,
                        border=ft.border.all(1, "#1e293b")
                    )
                )
        else:
            active_count = len(store.active)
            subtitle_text.value = f"Batutda olan uşaqlar: {active_count} nəfər"
            items = []
            for c in store.active:
                if c.get("exit") is None:
                    remaining = float('inf')
                else:
                    exit_dt = datetime.fromisoformat(c["exit"])
                    remaining = (exit_dt - n).total_seconds()
                items.append((remaining, c))
            
            # Sıralama: limitsizlər sona, qalanlar azalan vaxta görə
            items.sort(key=lambda x: (x[0] == float('inf'), x[0]))
            
            if not items:
                list_column.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text("🎈", size=50),
                            ft.Text("Hazırda batutda uşaq yoxdur", color=MUTED, size=15, weight=ft.FontWeight.BOLD),
                            ft.Text("Yeni uşaq əlavə etmək üçün aşağıdakı düyməni istifadə edin.", color=MUTED, size=12, text_align=ft.TextAlign.CENTER)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                        padding=60, alignment=ft.alignment.center
                    )
                )
            for remaining, c in items:
                list_column.controls.append(build_card(c, remaining))
        
        page.update()

    # ---------- Vaxt Artırma və Silmə Əməliyyatları ----------
    async def extend_time(child_id, minutes):
        for c in store.active:
            if c["id"] == child_id and c.get("exit"):
                exit_dt = datetime.fromisoformat(c["exit"])
                c["exit"] = (exit_dt + timedelta(minutes=minutes)).isoformat()
                if child_id in state["alerted_ids"]:
                    state["alerted_ids"].discard(child_id)
                await store.save()
                break
        render()

    async def manual_remove(child_id, page):
        target = next((c for c in store.active if c["id"] == child_id), None)
        if not target:
            return

        def confirm_yes(e):
            page.run_task(do_remove)
            hide_modal()

        async def do_remove():
            await store.move_to_log(target, status="Əl ilə silinib")
            render()

        def confirm_no(e):
            hide_modal()

        box = ft.Column(
            [
                ft.Text("Təsdiq Et", size=18, weight=ft.FontWeight.BOLD, color=TEXT),
                ft.Text(f"'{target['name']}' siyahıdan silinsin?", color=MUTED, size=14),
                ft.Row(
                    [
                        ft.TextButton("Xeyr", on_click=confirm_no),
                        ft.ElevatedButton("Bəli, Sil", bgcolor=RED, color=WHITE, on_click=confirm_yes,
                                         style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                    spacing=10,
                ),
            ],
            tight=True, spacing=14,
        )
        show_modal(box)

    # ---------- Vaxtı Bitən Uşaq Üçün Xəbərdarlıq ----------
    def show_expire_alert(child):
        state["alert_open"] = True

        def close_alert(e):
            hide_modal()
            state["alert_open"] = False
            process_alert_queue()

        note_controls = []
        if child.get("note"):
            note_controls = [
                ft.Container(
                    content=ft.Column([
                        ft.Text("Qeyd:", size=12, weight=ft.FontWeight.BOLD, color="#fecaca"),
                        ft.Text(child["note"], size=14, color=WHITE),
                    ], spacing=2),
                    bgcolor="#991b1b", border_radius=10, padding=12, width=320
                )
            ]

        box = ft.Column(
            [
                ft.Text("⏰", size=40, text_align=ft.TextAlign.CENTER),
                ft.Text(f"{child['name']} üçün vaxt bitdi!", size=20, weight=ft.FontWeight.BOLD, color=WHITE, text_align=ft.TextAlign.CENTER),
                *note_controls,
                ft.ElevatedButton(
                    "Anladım / Bağla", bgcolor=WHITE, color=RED,
                    on_click=close_alert,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=12)
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
            tight=True,
        )
        show_modal(box, box_bgcolor=RED)

    def process_alert_queue():
        if state["alert_open"] or not state["alert_queue"]:
            return
        child = state["alert_queue"].pop(0)
        show_expire_alert(child)

    # ---------- Yeni Uşaq Əlavə Etmə Dialoqu (30 dq, 60 dq, Limitsiz) ----------
    def open_add_child(e):
        name_fields_col = ft.Column(spacing=8)
        name_entries = []

        def add_name_row(first=False):
            tf = ft.TextField(
                label="Uşağın adı və soyadı" if first else "Növbəti uşağın adı",
                bgcolor=CARD_BG, color=TEXT, border_radius=10,
                border_color="#334155", focused_border_color=ACCENT,
                text_size=14, height=50
            )
            name_entries.append(tf)
            row_controls = [tf]
            if not first:
                def remove_this(ev, tf=tf):
                    if tf in name_entries:
                        name_entries.remove(tf)
                    for row in list(name_fields_col.controls):
                        if tf in row.controls:
                            name_fields_col.controls.remove(row)
                            break
                    page.update()

                row_controls.append(
                    ft.IconButton(ft.Icons.CLOSE, icon_color=MUTED, on_click=remove_this)
                )
            row = ft.Row(row_controls, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            name_fields_col.controls.append(row)

        add_name_row(first=True)

        add_row_btn = ft.TextButton(
            "＋ Eyni anda gələn başqa uşaq əlavə et",
            on_click=lambda e: (add_name_row(), page.update()),
        )

        entry_time_text = ft.Text(fmt_time(now()), size=14, weight=ft.FontWeight.BOLD, color=GREEN)

        # Seçimlər: 30 dəq, 60 dəq, Limitsiz (90 və 120 silindi)
        duration_state = {"value": 30}
        duration_buttons = {}

        def select_duration(val):
            duration_state["value"] = val
            for v, b in duration_buttons.items():
                if v == val:
                    b.bgcolor = ACCENT
                    b.color = "#070b19"
                else:
                    b.bgcolor = CARD_BG
                    b.color = TEXT
            page.update()

        durations_def = [
            (30, "30 dəq"),
            (60, "60 dəq"),
            (None, "Limitsiz ∞")
        ]

        dur_row = ft.Row(spacing=8, alignment=ft.MainAxisAlignment.CENTER)
        for val, label in durations_def:
            btn = ft.ElevatedButton(
                label,
                bgcolor=ACCENT if val == 30 else CARD_BG,
                color="#070b19" if val == 30 else TEXT,
                on_click=lambda e, v=val: select_duration(v),
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=10),
                expand=True
            )
            duration_buttons[val] = btn
            dur_row.controls.append(btn)

        note_field = ft.TextField(
            label="Qeyd / Xüsusi istək (istəyə bağlı)",
            bgcolor=CARD_BG, color=TEXT, border_radius=10,
            border_color="#334155", focused_border_color=ACCENT,
            text_size=13, height=45
        )

        async def save_children(e):
            n_val = now()
            added_any = False
            for tf in name_entries:
                val_name = tf.value.strip() if tf.value else ""
                if val_name:
                    added_any = True
                    dur = duration_state["value"]
                    exit_dt = (n_val + timedelta(minutes=dur)) if dur is not None else None
                    child = await store.add_child(val_name, n_val, exit_dt, note_field.value.strip())
                    state["new_ids"].add(child["id"])
            if added_any:
                hide_modal()
                render()

        content_col = ft.Column(
            [
                ft.Text("Yeni Uşaq Qeydiyyatı", size=18, weight=ft.FontWeight.BOLD, color=TEXT),
                ft.Row([ft.Text("Giriş vaxtı:", size=13, color=MUTED), entry_time_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                name_fields_col,
                add_row_btn,
                ft.Text("Seans müddəti:", size=13, color=MUTED),
                dur_row,
                note_field,
                ft.Row(
                    [
                        ft.TextButton("İmtina", on_click=hide_modal),
                        ft.ElevatedButton("Təsdiq Et & Başlat", bgcolor=GREEN, color=WHITE, on_click=save_children,
                                         style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            tight=True, spacing=10, width=330
        )
        show_modal(content_col)

    # ---------- Naviqasiya Başlığı (Header) ----------
    def switch_view(view_name):
        state["view"] = view_name
        if view_name == "main":
            tab_active_btn.bgcolor = ACCENT
            tab_active_btn.color = "#070b19"
            tab_logs_btn.bgcolor = CARD_BG
            tab_logs_btn.color = TEXT
        else:
            tab_logs_btn.bgcolor = ACCENT
            tab_logs_btn.color = "#070b19"
            tab_active_btn.bgcolor = CARD_BG
            tab_active_btn.color = TEXT
        render()

    tab_active_btn = ft.ElevatedButton("Aktivlər", bgcolor=ACCENT, color="#070b19", on_click=lambda e: switch_view("main"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
    tab_logs_btn = ft.ElevatedButton("Tarixçə", bgcolor=CARD_BG, color=TEXT, on_click=lambda e: switch_view("logs"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))

    header_row = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Container(content=ft.Text("🚀", size=18), bgcolor="#1e293b", padding=8, border_radius=10),
                ft.Column([
                    ft.Text("TOP-TOP", size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text("Əyləncə Mərkəzi", size=10, color=ACCENT)
                ], spacing=0)
            ], spacing=8),
            ft.Row([tab_active_btn, tab_logs_btn], spacing=6)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=12, bgcolor="#0f172a", border=ft.border.only(bottom=ft.BorderSide(1, "#1e293b"))
    )

    # ---------- Əsas Səhifə Struktur (Layout) ----------
    body_container = ft.Container(
        content=ft.Column([
            header_row,
            ft.Container(
                content=ft.Row([subtitle_text], alignment=ft.MainAxisAlignment.START),
                padding=ft.padding.symmetric(horizontal=16, vertical=4)
            ),
            ft.Container(content=list_column, expand=True, padding=ft.padding.symmetric(horizontal=8)),
            
            # Alt Əlavə Et Düyməsi və Owner Bilgisi
            ft.Container(
                content=ft.Column([
                    ft.ElevatedButton(
                        "＋ Yeni Uşaq Əlavə Et",
                        bgcolor=ACCENT,
                        color="#070b19",
                        on_click=open_add_child,
                        width=float("inf"),
                        height=48,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=12),
                            text_style=ft.TextStyle(size=15, weight=ft.FontWeight.BOLD)
                        )
                    ),
                    ft.Container(
                        content=ft.Text("Owner by Sərkər Qubadov", size=11, color=MUTED, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER),
                        alignment=ft.alignment.center,
                        padding=ft.padding.only(top=6)
                    )
                ], spacing=4),
                padding=12,
                bgcolor="#0f172a",
                border=ft.border.only(top=ft.BorderSide(1, "#1e293b"))
            )
        ], spacing=0),
        expand=True
    )

    page.add(
        ft.Stack([
            body_container,
            overlay_container,
        ], expand=True)
    )

    render()

    # ---------- Fon Proseslər (Timer və Yenilənmə) ----------
    async def background_loop():
        blink_counter = 0
        while True:
            await asyncio.sleep(1)
            await store.check_daily_reset()
            
            n = now()
            state["blink_on"] = not state["blink_on"]
            
            # Vaxtı bitənləri yoxla
            for c in list(store.active):
                if c.get("exit") is None:
                    continue
                exit_dt = datetime.fromisoformat(c["exit"])
                rem = (exit_dt - n).total_seconds()
                
                if rem <= 0 and c["id"] not in state["alerted_ids"]:
                    state["alerted_ids"].add(c["id"])
                    state["alert_queue"].append(c)
                    if not state["alert_open"]:
                        process_alert_queue()
            
            if state["view"] == "main":
                render()

    page.run_task(background_loop)

if __name__ == "__main__":
    ft.app(target=main)
```eof

### Əsas Edilən Dəyişikliklər və Yeniliklər:
1. **Mobil Tam Uyğunluq (Responsive & Full Phone Setup):** Bütün elementlər, düymələr və grid strukturları smartfon ekranlarında kənara daşmayacaq, tam səliqəli yerləşəcək şəkildə konfiqurasiya edildi.
2. **Müddət Seçimləri:** İstəyinizə uyğun olaraq 90 və 120 dəqiqə seçimləri tamamilə silindi, yerində yalnız **30 dəq**, **60 dəq** və **Limitsiz ∞** seçimləri saxlanıldı.
3. **Deluxe & Premium Dizayn + Animasiyalar:** Müasir tünd göy, cyan (neon mavi) və qızılı elementlərdən ibarət rəng palitrası tətbiq olundu. Kartların açılış/keçid animasiyaları və modal pəncərələrin şık görünüşü gücləndirildi.
4. **Azərbaycan Əlifbası Dəstəyi:** UTF-8 kodlaşdırması və Azərbaycan hərfləri (`ə, ç, ö, ğ, ü, ş, ı`) üçün tam dəstək təmin edildi.
5. **Mütləq İmza:** Proqramın ən aşağı hissəsində tələb olunduğu kimi **"Owner by Sərkər Qubadov"** imzası əlavə edildi.

Seanslarınızı problemsiz idarə etməniz diləyi ilə!
