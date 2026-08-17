# -*- coding: utf-8 -*-
"""
TOP - TOP Əyləncə Mərkəzi (Flet versiyası - Android APK üçün)

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

# ---------------- Rənglər ----------------
BG = "#0f172a"
CARD_BG = "#1e293b"
CARD_WARN = "#4c1d1d"
CARD_WARN2 = "#7f1d1d"
ACCENT = "#38bdf8"
GREEN = "#22c55e"
ORANGE = "#f59e0b"
RED = "#ef4444"
TEXT = "#f1f5f9"
MUTED = "#94a3b8"
WHITE = "#ffffff"


def now():
    return datetime.now()


def fmt_time(dt):
    return dt.strftime("%H:%M")


def fmt_remaining(seconds):
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
            "exit": exit_dt.isoformat(),
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

    store = Store(page)
    await store.load()

    state = {
        "view": "main",           # "main" | "logs"
        "alerted_ids": set(),
        "new_ids": set(),
        "alert_queue": [],
        "alert_open": False,
        "blink_on": False,
    }

    list_column = ft.ListView(expand=True, spacing=8, padding=16, auto_scroll=False)
    subtitle_text = ft.Text("Batutda olan uşaqlar", size=13, color=MUTED)

    # ---------- Universal overlay ----------
    overlay_container = ft.Container(
        visible=False,
        bgcolor="#000000CC",
        left=0, top=0, right=0, bottom=0,
        padding=20,
    )

    def show_modal(inner_content, box_bgcolor=None):
        box = ft.Container(
            content=inner_content,
            bgcolor=box_bgcolor or CARD_BG,
            border_radius=16,
            padding=22,
            width=440,
        )
        overlay_container.content = ft.Row(
            [box],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )
        overlay_container.visible = True
        page.update()

    def hide_modal(e=None):
        overlay_container.visible = False
        page.update()

    # ---------- Kart qurma ----------
    def build_card(c, remaining):
        is_warn = 0 < remaining <= 180
        bg = CARD_WARN if is_warn else CARD_BG
        if is_warn and state["blink_on"]:
            bg = CARD_WARN2

        timer_color = GREEN if remaining > 300 else (ORANGE if remaining > 180 else RED)

        info_text = (
            f"Giriş: {fmt_time(datetime.fromisoformat(c['entry']))}   →   "
            f"Çıxış: {fmt_time(datetime.fromisoformat(c['exit']))}"
        )

        left_items = [
            ft.Text(c["name"], size=18, weight=ft.FontWeight.BOLD, color=TEXT),
            ft.Text(info_text, size=12, color=MUTED),
        ]
        if c.get("note"):
            left_items.append(ft.Text(f"📝 {c['note']}", size=12, color=ACCENT))

        async def on_extend(e, cid=c["id"]):
            await extend_time(cid, 30)

        async def on_delete(e, cid=c["id"]):
            await manual_remove(cid, page)

        right_items = ft.Column(
            [
                ft.Text(fmt_remaining(remaining), size=24, weight=ft.FontWeight.BOLD, color=timer_color),
                ft.Row(
                    [
                        ft.Button(
                            "+30 dəq", bgcolor=ACCENT, color="#082032",
                            on_click=on_extend, height=34,
                        ),
                        ft.OutlinedButton("Sil", height=34, on_click=on_delete),
                    ],
                    spacing=6,
                ),
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
            ),
            bgcolor=bg,
            border_radius=14,
            padding=16,
            animate=ft.Animation(350, ft.AnimationCurve.EASE_IN_OUT),
            animate_opacity=300,
            opacity=1,
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

    # ---------- Render ----------
    def render():
        list_column.controls.clear()
        n = now()
        if state["view"] == "logs":
            if not store.logs:
                list_column.controls.append(
                    ft.Text("Bugün üçün log qeydi yoxdur", color=MUTED, size=14)
                )
            for log in store.logs:
                entry_t = fmt_time(datetime.fromisoformat(log["entry"]))
                exit_t = fmt_time(datetime.fromisoformat(log["exit"]))
                removed_t = fmt_time(datetime.fromisoformat(log["removed_at"]))
                items = [
                    ft.Text(log["name"], size=18, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text(
                        f"Giriş: {entry_t}   Planlaşan: {exit_t}   Faktiki: {removed_t}",
                        size=12, color=MUTED,
                    ),
                ]
                if log.get("note"):
                    items.append(ft.Text(f"📝 {log['note']}", size=12, color=ACCENT))
                list_column.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Column(items, expand=True, spacing=2),
                                ft.Text(log.get("status", "Bitib"), size=12,
                                        weight=ft.FontWeight.BOLD,
                                        color=RED if "bitib" in log.get("status", "").lower() else MUTED),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        bgcolor=CARD_BG, border_radius=14, padding=16,
                    )
                )
        else:
            items = []
            for c in store.active:
                exit_dt = datetime.fromisoformat(c["exit"])
                remaining = (exit_dt - n).total_seconds()
                items.append((remaining, c))
            items.sort(key=lambda x: x[0])
            if not items:
                list_column.controls.append(
                    ft.Text("Hazırda batutda uşaq yoxdur 🎈", color=MUTED, size=14)
                )
            for remaining, c in items:
                list_column.controls.append(build_card(c, remaining))
        page.update()

    # ---------- Vaxt artırma / silmə ----------
    async def extend_time(child_id, minutes):
        for c in store.active:
            if c["id"] == child_id:
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
                ft.Text("Təsdiq", size=18, weight=ft.FontWeight.BOLD, color=TEXT),
                ft.Text(f"{target['name']} siyahıdan silinsin?", color=TEXT),
                ft.Row(
                    [
                        ft.TextButton("Xeyr", on_click=confirm_no),
                        ft.Button("Bəli", bgcolor=RED, color=WHITE, on_click=confirm_yes),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            tight=True, spacing=14,
        )
        show_modal(box)

    # ---------- Vaxtı bitən uşaq üçün tam ekran xəbərdarlıq ----------
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
                    content=ft.Column(
                        [
                            ft.Text("Qeyd:", size=13, weight=ft.FontWeight.BOLD, color="#fecaca"),
                            ft.Text(child["note"], size=16, color=WHITE),
                        ],
                        spacing=6,
                    ),
                    bgcolor="#991b1b", border_radius=10, padding=16,
                )
            ]

        box = ft.Column(
            [
                ft.Text("⏰", size=50, text_align=ft.TextAlign.CENTER),
                ft.Text(f"{child['name']} üçün vaxt bitib!",
                        size=24, weight=ft.FontWeight.BOLD, color=WHITE,
                        text_align=ft.TextAlign.CENTER),
                *note_controls,
                ft.Button(
                    "Anladım / Bağla", bgcolor=WHITE, color=RED,
                    on_click=close_alert,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16,
            tight=True,
        )
        show_modal(box, box_bgcolor=RED)

    def process_alert_queue():
        if state["alert_open"] or not state["alert_queue"]:
            return
        child = state["alert_queue"].pop(0)
        show_expire_alert(child)

    # ---------- Uşaq əlavə etmə dialoqu ----------
    def open_add_child(e):
        name_fields_col = ft.Column(spacing=8)
        name_entries = []

        def add_name_row(first=False):
            tf = ft.TextField(label="Uşağın adı" if first else "Növbəti uşağın adı",
                               bgcolor=CARD_BG, color=TEXT, border_radius=8,
                               border_color="#334155")
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
            row = ft.Row(row_controls)
            name_fields_col.controls.append(row)

        add_name_row(first=True)

        add_row_btn = ft.TextButton(
            "＋ Daha bir uşaq əlavə et (eyni anda gələnlər üçün)",
            on_click=lambda e: (add_name_row(), page.update()),
        )

        entry_time_text = ft.Text(fmt_time(now()), size=16, weight=ft.FontWeight.BOLD, color=GREEN)

        duration_state = {"value": 30}
        duration_buttons = {}

        def select_duration(v):
            duration_state["value"] = v
            for val, b in duration_buttons.items():
                b.bgcolor = ACCENT if val == v else CARD_BG
                b.color = "#082032" if val == v else TEXT
            page.update()

        dur_row_controls = []
        for val in (30, 60, 90, 120):
            b = ft.Button(
                f"{val} dəq",
                bgcolor=ACCENT if val == 30 else CARD_BG,
                color="#082032" if val == 30 else TEXT,
                on_click=lambda e, v=val: select_duration(v),
            )
            duration_buttons[val] = b
            dur_row_controls.append(b)

        custom_minutes = ft.TextField(
            label="Digər (dəqiqə)", width=140, bgcolor=CARD_BG, color=TEXT,
            border_color="#334155", keyboard_type=ft.KeyboardType.NUMBER,
        )

        def apply_custom(e):
            try:
                v = int(custom_minutes.value)
                duration_state["value"] = v
                for b in duration_buttons.values():
                    b.bgcolor = CARD_BG
                    b.color = TEXT
                page.update()
            except (ValueError, TypeError):
                pass

        note_field = ft.TextField(
            label="Xüsusi qeyd (valideyndən)", multiline=True, min_lines=2, max_lines=4,
            bgcolor=CARD_BG, color=TEXT, border_color="#334155",
        )

        def cancel(e):
            hide_modal()

        async def submit(e):
            names = [tf.value.strip() for tf in name_entries if tf.value and tf.value.strip()]
            if not names:
                name_entries[0].error_text = "Ən azı bir ad daxil edin"
                page.update()
                return
            entry_dt = now()
            exit_dt = entry_dt + timedelta(minutes=duration_state["value"])
            note = note_field.value.strip() if note_field.value else ""
            for nm in names:
                child = await store.add_child(nm, entry_dt, exit_dt, note)
                state["new_ids"].add(child["id"])
            hide_modal()
            state["view"] = "main"
            subtitle_text.value = "Batutda olan uşaqlar"
            render()

        box = ft.Column(
            [
                ft.Text("Yeni Uşaq Əlavə Et", size=18, weight=ft.FontWeight.BOLD, color=TEXT),
                name_fields_col,
                add_row_btn,
                ft.Divider(color="#334155"),
                ft.Text("Daxil olma vaxtı", size=12, color=MUTED),
                entry_time_text,
                ft.Text("Çıxış müddəti (dəqiqə)", size=12, color=MUTED),
                ft.Row(dur_row_controls, wrap=True),
                ft.Row([custom_minutes, ft.Button("Tətbiq et", on_click=apply_custom)]),
                note_field,
                ft.Row(
                    [
                        ft.TextButton("Ləğv Et", on_click=cancel),
                        ft.Button("Əlavə Et", bgcolor=GREEN, color="#052e16",
                                  on_click=lambda e: page.run_task(submit, e)),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=10, scroll=ft.ScrollMode.AUTO, tight=True,
            height=560,
        )
        show_modal(box)

    # ---------- Naviqasiya ----------
    def toggle_view(e):
        state["view"] = "logs" if state["view"] == "main" else "main"
        if state["view"] == "logs":
            nav_btn.text = "⬅ Geri"
            subtitle_text.value = "Günün logları (hər gün 05:00-da sıfırlanır)"
        else:
            nav_btn.text = "🗂 Loglar"
            subtitle_text.value = "Batutda olan uşaqlar"
        render()

    nav_btn = ft.OutlinedButton("🗂 Loglar", on_click=toggle_view)
    add_btn = ft.Button(
        "＋ Uşaq Əlavə Et", bgcolor=GREEN, color="#052e16", on_click=open_add_child
    )

    header = ft.Container(
        content=ft.Column(
            [
                ft.Text("🎪 TOP - TOP Əyləncə Mərkəzi", size=18, weight=ft.FontWeight.BOLD, color=TEXT),
                subtitle_text,
                ft.Row([nav_btn, add_btn], spacing=10, wrap=True),
            ],
            spacing=8,
        ),
        padding=16,
        bgcolor=BG,
    )

    page.add(
        ft.Stack(
            [
                ft.Column(
                    [header, ft.Divider(color="#1e293b", height=1), list_column],
                    expand=True, spacing=0,
                ),
                overlay_container,
            ],
            expand=True,
        )
    )

    # ---------- Əsas dövr (saniyədə bir) ----------
    async def clock_loop():
        while True:
            await store.check_daily_reset()
            n = now()
            expired_now = []
            for c in list(store.active):
                exit_dt = datetime.fromisoformat(c["exit"])
                remaining = (exit_dt - n).total_seconds()
                if remaining <= 0 and c["id"] not in state["alerted_ids"]:
                    state["alerted_ids"].add(c["id"])
                    expired_now.append(c)

            # Vaxtı bitənləri xəbərdarlıq növbəsinə əlavə et
            for c in expired_now:
                state["alert_queue"].append(c)
            if expired_now:
                process_alert_queue()

            # Xəbərdarlıq rənginin yanıb-sönməsi üçün
            state["blink_on"] = not state["blink_on"]

            render()
            await asyncio.sleep(1)

    page.run_task(clock_loop)


ft.app(target=main)
