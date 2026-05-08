import tkinter as tk
from tkinter import filedialog, ttk, colorchooser, simpledialog
import tkinter.font as tkfont
from PIL import ImageGrab, Image, ImageDraw, ImageTk, ImageOps, ImageFilter, ImageFont, ImageEnhance
import time
import os
import ctypes
from ctypes import wintypes
import io
import json
import math
import keyboard  # pip install keyboard
import pystray   # pip install pystray
import threading
import sys
import winreg

# DPI 인식 설정
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- [64비트 호환성 유지] Windows API 정의 ---
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
msvcrt = ctypes.cdll.msvcrt

user32.OpenClipboard.argtypes = [ctypes.c_void_p]
user32.OpenClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
user32.SetClipboardData.restype = ctypes.c_void_p
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL

kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.restype = wintypes.BOOL

msvcrt.memcpy.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
msvcrt.memcpy.restype = ctypes.c_void_p
# -------------------------------------------

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "settings.json")

class ResizableBox(tk.Toplevel):
    def __init__(self, parent, width, height, on_capture):
        super().__init__(parent)
        self.on_capture = on_capture
        self.top_bar_h = 40    
        self.sw, self.sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{width}x{height + self.top_bar_h}+200+200")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.config(bg='white')
        self.attributes("-transparentcolor", "white")
        
        self.bar_position = "top"
        self.top_frame = tk.Frame(self, bg='#1e1e1e', height=self.top_bar_h)
        self.top_frame.pack(fill=tk.X, side=tk.TOP)
        self.top_frame.pack_propagate(False)

        self.info_label = tk.Label(self.top_frame, text=f"{width} x {height}", 
                                   bg='#1e1e1e', fg='#f1c40f', font=("Malgun Gothic", 12, "bold"))
        self.info_label.pack(side=tk.LEFT, padx=15)

        self.close_btn = tk.Button(self.top_frame, text=" ✕ ", bg='#1e1e1e', fg='#f1c40f', 
                                   command=self.close_box, bd=0, font=("Arial", 14, "bold"), 
                                   activebackground='#e81123', cursor="hand2")
        self.close_btn.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.cap_btn = tk.Button(self.top_frame, text=" CAPTURE(Enter) ", bg="#00ff7f", fg="#000000", 
                                 command=self.trigger_capture, font=("Malgun Gothic", 9, "bold"),
                                 cursor="hand2", bd=0, padx=15, pady=3)
        self.cap_btn.pack(side=tk.RIGHT, padx=10, pady=5)

        self.canvas = tk.Canvas(self, bg='white', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.rect = self.canvas.create_rectangle(0, 0, width, height, outline="#ff4757", width=4)
        
        self.catcher = tk.Toplevel(self)
        self.catcher.overrideredirect(True)
        self.catcher.config(bg="white")
        self.catcher.attributes("-alpha", 0.01)
        self.catcher.attributes("-topmost", True)
        
        self.focus_force()
        self.catcher.focus_force()

        self.top_frame.bind("<Button-1>", self.start_move)
        self.top_frame.bind("<B1-Motion>", self.do_move)
        self.catcher.bind("<Button-1>", self.start_resize)
        self.catcher.bind("<B1-Motion>", self.do_resize)
        self.catcher.bind("<Motion>", self.update_cursor)
        self.bind("<Escape>", lambda e: self.close_box())
        self.bind("<Return>", lambda e: self.trigger_capture())
        self.catcher.bind("<Return>", lambda e: self.trigger_capture())
        self.bind("<Configure>", self.sync_ui)

    def close_box(self):
        if hasattr(self, 'catcher') and self.catcher.winfo_exists():
            self.catcher.destroy()
        self.master.deiconify()
        self.master.attributes("-topmost", True)
        self.destroy()

    def sync_ui(self, event=None):
        w, h = self.winfo_width(), self.winfo_height() - self.top_bar_h
        self.canvas.coords(self.rect, 2, 2, w-2, h-2)
        self.info_label.config(text=f"{w} x {h}")
        
        if self.winfo_y() < self.top_bar_h:
            if self.bar_position != "bottom":
                self.top_frame.pack_forget()
                self.canvas.pack_forget()
                self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                self.top_frame.pack(side=tk.BOTTOM, fill=tk.X)
                self.bar_position = "bottom"
        else:
            if self.bar_position != "top":
                self.top_frame.pack_forget()
                self.canvas.pack_forget()
                self.top_frame.pack(side=tk.TOP, fill=tk.X)
                self.canvas.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
                self.bar_position = "top"
                
        if hasattr(self, 'catcher') and self.catcher.winfo_exists():
            cx = self.winfo_x()
            cy = self.winfo_y() + (self.top_bar_h if self.bar_position == "top" else 0)
            self.catcher.geometry(f"{max(1, w)}x{max(1, h)}+{cx}+{cy}")

    def update_cursor(self, event):
        if not hasattr(self, 'catcher') or not self.catcher.winfo_exists(): return
        m, w, h = 15, self.canvas.winfo_width(), self.canvas.winfo_height()
        is_l, is_r, is_t, is_b = event.x < m, event.x > w - m, event.y < m, event.y > h - m
        if (is_l and is_t) or (is_r and is_b): c = "size_nw_se"
        elif (is_r and is_t) or (is_l and is_b): c = "size_ne_sw"
        elif is_l or is_r: c = "size_we"
        elif is_t or is_b: c = "size_ns"
        else: c = "fleur"
        self.catcher.config(cursor=c)

    def start_move(self, event):
        self.focus_force()
        self.rx = event.x_root
        self.ry = event.y_root
        self.wx = self.winfo_x()
        self.wy = self.winfo_y()

    def do_move(self, event):
        dx = event.x_root - self.rx
        dy = event.y_root - self.ry
        x = max(0, min(self.sw - self.winfo_width(), self.wx + dx))
        y = max(0, min(self.sh - self.winfo_height(), self.wy + dy))
        self.geometry(f"+{x}+{y}")

    def start_resize(self, event):
        if not hasattr(self, 'catcher') or not self.catcher.winfo_exists(): return
        self.focus_force()
        self.catcher.focus_force()
        m, w, h = 15, self.canvas.winfo_width(), self.canvas.winfo_height()
        is_l, is_r, is_t, is_b = event.x < m, event.x > w - m, event.y < m, event.y > h - m
        if is_l or is_r or is_t or is_b:
            self.action_mode = "resize"
            self.sww, self.shh, self.sx, self.sy = self.winfo_width(), self.winfo_height(), event.x_root, event.y_root
        else:
            self.action_mode = "move"
            self.start_move(event)

    def do_resize(self, event):
        if getattr(self, "action_mode", "resize") == "move":
            self.do_move(event)
            return

        dx, dy = event.x_root - self.sx, event.y_root - self.sy
        new_w = max(250, min(self.sw - self.winfo_x(), self.sww + dx))
        if event.state & 0x0001:
            ratio = self.sww / (self.shh - self.top_bar_h)
            new_h = int((new_w / ratio) + self.top_bar_h)
            if new_h > self.sh - self.winfo_y():
                new_h = self.sh - self.winfo_y()
                new_w = int((new_h - self.top_bar_h) * ratio)
        else:
            new_h = max(150, min(self.sh - self.winfo_y(), self.shh + dy))
        self.geometry(f"{new_w}x{new_h}")

    def trigger_capture(self):
        w, h = self.winfo_width(), self.winfo_height() - self.top_bar_h
        x = self.winfo_x()
        y = self.winfo_y() + self.top_bar_h if self.bar_position == "top" else self.winfo_y()
        if hasattr(self, 'catcher') and self.catcher.winfo_exists():
            self.catcher.destroy()
        self.withdraw(); self.update(); time.sleep(0.2)
        self.on_capture(x, y, x + w, y + h)
        self.deiconify(); self.attributes("-topmost", True)

class ImageEditor(tk.Toplevel):
    """캡처 이미지 편집기 — 더블클릭으로 열림"""
    MAX_UNDO = 10
    PALETTE = ["#FF0000","#FF6600","#FFCC00","#00BB00","#0055FF",
               "#9900CC","#FFFFFF","#AAAAAA","#555555","#000000",
               "#FF99BB","#00CCCC"]

    def __init__(self, parent, filepath, app):
        super().__init__(parent)
        self.filepath = filepath
        self.app = app          # MainApp 참조
        self.attributes("-topmost", True)
        self.resizable(True, True)
        self.title(f"편집기 — {os.path.basename(filepath)}")

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        target_w = int(sw * 0.75)
        target_h = int(target_w * 9 / 16)
        x = (sw - target_w) // 2
        y = (sh - target_h) // 2
        self.geometry(f"{target_w}x{target_h}+{x}+{y}")

        # ── 이미지 상태 ──────────────────────────────────────
        raw = Image.open(filepath)
        self.edit_img = raw.convert("RGBA")
        self.undo_stack = []
        self.redo_stack = []

        # ── 도구 상태 ─────────────────────────────────────────
        self.current_tool = "pen"
        self.draw_color   = "#FF0000"
        self.custom_fill_color = None
        self.line_width   = 3
        self.font_family  = "Malgun Gothic"
        self.font_size    = 20

        # ── 드로잉 임시 변수 ──────────────────────────────────
        self._sx = self._sy = 0
        self._temp_items = []
        self._pen_pts    = []
        self.scale       = 1.0
        self._tk_img     = None
        self._tool_btns  = {}

        self._build_ui()
        self.after(50, self._fit_and_refresh)
        self._bind_events()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # ══════════════════════════════════════════════
    #  UI 구성
    # ══════════════════════════════════════════════
    def _build_ui(self):
        # ── 상단 툴바 영역 ────────────────────────────
        top_area = tk.Frame(self, bg="#1e272e")
        top_area.pack(fill=tk.X)
        
        bs = dict(bg="#485460", fg="white", font=("Malgun Gothic", 9, "bold"),
                  bd=0, padx=12, pady=6, cursor="hand2",
                  activebackground="#0fbcf9", activeforeground="white")

        # 1행: 파일/편집 옵션 + 해상도 표시
        row1 = tk.Frame(top_area, bg="#1e272e", pady=8, padx=12)
        row1.pack(fill=tk.X)
        
        tk.Button(row1, text="💾 저장",        command=self.save,              **bs).pack(side=tk.LEFT, padx=3)
        tk.Button(row1, text="📁 다른이름저장", command=self.save_as,           **bs).pack(side=tk.LEFT, padx=3)
        tk.Button(row1, text="📋 클립보드",     command=self.copy_to_clipboard, **bs).pack(side=tk.LEFT, padx=3)
        tk.Frame(row1, bg="#808e9b", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=4)
        tk.Button(row1, text="↩ 실행취소",     command=self.undo,              **bs).pack(side=tk.LEFT, padx=2)
        tk.Button(row1, text="↪ 재실행",       command=self.redo,              **bs).pack(side=tk.LEFT, padx=2)
        tk.Frame(row1, bg="#808e9b", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=4)
        tk.Button(row1, text="↺ 90°",          command=lambda: self.rotate(-90),**bs).pack(side=tk.LEFT, padx=2)
        tk.Button(row1, text="↻ 90°",          command=lambda: self.rotate(90), **bs).pack(side=tk.LEFT, padx=2)
        tk.Button(row1, text="↔ 좌우반전",     command=lambda: self.flip("h"), **bs).pack(side=tk.LEFT, padx=2)
        tk.Button(row1, text="↕ 상하반전",     command=lambda: self.flip("v"), **bs).pack(side=tk.LEFT, padx=2)
        
        self._size_lbl = tk.Label(row1, text="", bg="#1e272e", fg="#00d8d6", font=("Arial", 10, "bold"))
        self._size_lbl.pack(side=tk.RIGHT, padx=10)

        # 2행: 도구 선택
        row2 = tk.Frame(top_area, bg="#2f3640", pady=10, padx=12)
        row2.pack(fill=tk.X)
        
        tk.Label(row2, text="도구:", bg="#2f3640", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0,10))
        
        tools = [("펜", "pen"), ("직선","line"), ("화살표","arrow"),
                 ("사각형","rect"), ("원","ellipse"), ("텍스트","text"),
                 ("형광펜","highlight"), ("모자이크","mosaic"), ("자르기","crop")]
        for label, name in tools:
            b = tk.Button(row2, text=label, height=1,
                          bg="#718093", fg="white", bd=0, cursor="hand2",
                          font=("Malgun Gothic", 9, "bold"), activebackground="#0fbcf9",
                          padx=14, pady=5,
                          command=lambda n=name: self._select_tool(n))
            b.pack(side=tk.LEFT, padx=3)
            self._tool_btns[name] = b
        self._select_tool("pen")

        # 3행: 색상, 두께, 폰트
        row3 = tk.Frame(top_area, bg="#1e272e", pady=10, padx=12)
        row3.pack(fill=tk.X)
        
        tk.Label(row3, text="선 색상:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0,6))
        for c in self.PALETTE:
            tk.Button(row3, bg=c, width=2, height=1, bd=1, relief="solid", cursor="hand2", command=lambda col=c: self._set_color(col)).pack(side=tk.LEFT, padx=2)
        tk.Button(row3, text="⊕", bg="#485460", fg="white", bd=0, cursor="hand2", font=("Arial",11), command=self._pick_color).pack(side=tk.LEFT, padx=6)
        self._color_ind = tk.Label(row3, bg=self.draw_color, width=3, height=1, relief="solid", bd=2)
        self._color_ind.pack(side=tk.LEFT, padx=4)

        tk.Frame(row3, bg="#808e9b", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=4)
        
        tk.Label(row3, text="채우기:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0,6))
        tk.Button(row3, text="자동", bg="#485460", fg="white", font=("Malgun Gothic", 8), bd=0, cursor="hand2", command=self._reset_fill_color).pack(side=tk.LEFT, padx=2)
        tk.Button(row3, text="⊕", bg="#485460", fg="white", bd=0, cursor="hand2", font=("Arial",11), command=self._pick_fill_color).pack(side=tk.LEFT, padx=2)
        self._fill_color_ind = tk.Label(row3, bg=self.draw_color, text="자동", fg="white", font=("Arial", 7), width=4, height=1, relief="solid", bd=2)
        self._fill_color_ind.pack(side=tk.LEFT, padx=4)

        tk.Frame(row3, bg="#808e9b", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=4)
        
        tk.Label(row3, text="두께:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0,6))
        self._width_var = tk.IntVar(value=self.line_width)
        tk.Spinbox(row3, from_=1, to=100, textvariable=self._width_var, width=4, font=("Arial", 10), command=lambda: setattr(self,"line_width",self._width_var.get())).pack(side=tk.LEFT)
                   
        tk.Frame(row3, bg="#808e9b", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=4)
        
        tk.Label(row3, text="글꼴:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0,6))
        self._font_var = tk.StringVar(value=self.font_family)
        ttk.Combobox(row3, textvariable=self._font_var, values=["Malgun Gothic", "Arial", "Consolas", "Impact"], state="readonly", width=12, font=("Arial", 9)).pack(side=tk.LEFT, padx=2)
        self._font_var.trace_add("write", lambda *a: setattr(self,"font_family",self._font_var.get()))

        tk.Label(row3, text="크기:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(8,4))
        self._fsize_var = tk.IntVar(value=self.font_size)
        tk.Spinbox(row3, from_=8, to=120, textvariable=self._fsize_var, width=4, font=("Arial", 10), command=lambda: setattr(self,"font_size",self._fsize_var.get())).pack(side=tk.LEFT)

        # ── 캔버스 영역 ─────────────────────────────
        self.canvas = tk.Canvas(self, bg="#2f3640", cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

    # ══════════════════════════════════════════════
    #  도구 선택 / 색상
    # ══════════════════════════════════════════════
    def _select_tool(self, name):
        self.current_tool = name
        for n, b in self._tool_btns.items():
            b.config(bg="#0fbcf9" if n == name else "#718093")

    def _set_color(self, color):
        self.draw_color = color
        self._color_ind.config(bg=color)
        if self.custom_fill_color is None:
            self._fill_color_ind.config(bg=color)

    def _pick_color(self):
        c = colorchooser.askcolor(color=self.draw_color, parent=self)[1]
        if c:
            self._set_color(c)

    def _pick_fill_color(self):
        c = colorchooser.askcolor(color=self.custom_fill_color or self.draw_color, parent=self)[1]
        if c:
            self.custom_fill_color = c
            self._fill_color_ind.config(bg=c, text="")

    def _reset_fill_color(self):
        self.custom_fill_color = None
        self._fill_color_ind.config(bg=self.draw_color, text="자동")

    # ══════════════════════════════════════════════
    #  캔버스 표시 (fit)
    # ══════════════════════════════════════════════
    def _fit_and_refresh(self):
        self.update_idletasks()
        cw = max(self.canvas.winfo_width(),  400)
        ch = max(self.canvas.winfo_height(), 300)
        iw, ih = self.edit_img.size
        self.scale = min(1.0, cw/iw, ch/ih)
        self._refresh_canvas()
        self._size_lbl.config(text=f"{iw} × {ih} px  ({self.scale*100:.0f}%)")

    def _refresh_canvas(self):
        iw, ih = self.edit_img.size
        dw = max(1, int(iw * self.scale))
        dh = max(1, int(ih * self.scale))
        disp = self.edit_img.convert("RGB").resize((dw, dh), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(disp)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

    def _c2i(self, cx, cy):
        """캔버스 → 이미지 좌표"""
        return int(cx / self.scale), int(cy / self.scale)

    # ══════════════════════════════════════════════
    #  이벤트 바인딩
    # ══════════════════════════════════════════════
    def _bind_events(self):
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",        self._on_drag)
        self.canvas.bind("<ButtonRelease-1>",  self._on_release)
        self.bind("<Control-z>",               lambda e: self.undo())
        self.bind("<Control-Z>",               lambda e: self.undo())
        self.bind("<Control-y>",               lambda e: self.redo())
        self.bind("<Control-Y>",               lambda e: self.redo())
        self.bind("<Configure>",               lambda e: self.after(10, self._fit_and_refresh))

    def _on_press(self, event):
        self._sx, self._sy = event.x, event.y
        self._pen_pts = [(event.x, event.y)]
        for item in self._temp_items:
            self.canvas.delete(item)
        self._temp_items = []

    def _on_drag(self, event):
        for item in self._temp_items:
            self.canvas.delete(item)
        self._temp_items = []
        x, y = event.x, event.y
        sx, sy = self._sx, self._sy
        col = self.draw_color
        lw  = self._width_var.get()
        t   = self.current_tool

        if t == "pen":
            self._pen_pts.append((x, y))
            pts = self._pen_pts
            if len(pts) >= 2:
                self._temp_items.append(
                    self.canvas.create_line(*pts[-2], *pts[-1], fill=col, width=lw,
                                           capstyle=tk.ROUND, joinstyle=tk.ROUND))
        elif t == "line":
            self._temp_items.append(self.canvas.create_line(sx,sy,x,y,fill=col,width=lw))
        elif t == "arrow":
            self._temp_items.append(self.canvas.create_line(sx,sy,x,y,fill=col,width=lw,
                                    arrow=tk.LAST, arrowshape=(16,20,6)))
        elif t == "rect":
            if getattr(self, "fill_shape_var", None) and self.fill_shape_var.get():
                fill_c = self.custom_fill_color or col
                self._temp_items.append(self.canvas.create_rectangle(sx,sy,x,y,fill=fill_c,outline=col,width=lw))
            else:
                self._temp_items.append(self.canvas.create_rectangle(sx,sy,x,y,outline=col,width=lw))
        elif t == "ellipse":
            if getattr(self, "fill_shape_var", None) and self.fill_shape_var.get():
                fill_c = self.custom_fill_color or col
                self._temp_items.append(self.canvas.create_oval(sx,sy,x,y,fill=fill_c,outline=col,width=lw))
            else:
                self._temp_items.append(self.canvas.create_oval(sx,sy,x,y,outline=col,width=lw))
        elif t == "highlight":
            self._temp_items.append(self.canvas.create_rectangle(sx,sy,x,y,
                                    fill=col, outline="", stipple="gray50"))
        elif t in ("mosaic","crop","text"):
            self._temp_items.append(self.canvas.create_rectangle(sx,sy,x,y,
                                    outline="#00FF00", width=2, dash=(6,4)))

    def _on_release(self, event):
        for item in self._temp_items:
            self.canvas.delete(item)
        self._temp_items = []
        x, y   = event.x, event.y
        sx, sy = self._sx, self._sy
        ix, iy   = self._c2i(x,  y)
        isx, isy = self._c2i(sx, sy)
        t = self.current_tool

        # ── 텍스트: 별도 팝업 처리 ─────────────────
        if t == "text":
            self._do_text(isx, isy)
            return

        # ── 크롭: 이미지 크기 변경 ─────────────────
        if t == "crop":
            x0,y0 = min(isx,ix), min(isy,iy)
            x1,y1 = max(isx,ix), max(isy,iy)
            iw, ih = self.edit_img.size
            x0,y0 = max(0,x0), max(0,y0)
            x1,y1 = min(iw,x1), min(ih,y1)
            if x1-x0 > 5 and y1-y0 > 5:
                self._push_undo()
                self.edit_img = self.edit_img.crop((x0,y0,x1,y1))
                self._fit_and_refresh()
            return

        # ── 나머지 도구: PIL에 그리기 ──────────────
        self._push_undo()
        draw = ImageDraw.Draw(self.edit_img)
        r,g,b = self._hex2rgb(self.draw_color)
        col_rgba = (r,g,b,255)
        lw = self.line_width

        if t == "pen":
            pts = [self._c2i(px,py) for px,py in self._pen_pts]
            if len(pts) >= 2:
                draw.line(pts, fill=col_rgba, width=lw, joint="curve")
            elif len(pts) == 1:
                r2 = max(1, lw//2)
                px,py = pts[0]
                draw.ellipse([px-r2,py-r2,px+r2,py+r2], fill=col_rgba)

        elif t == "line":
            draw.line([isx,isy,ix,iy], fill=col_rgba, width=lw)

        elif t == "arrow":
            self._draw_arrow(draw, isx,isy,ix,iy, col_rgba, lw)

        elif t == "rect":
            x0,y0 = min(isx,ix),min(isy,iy)
            x1,y1 = max(isx,ix),max(isy,iy)
            if getattr(self, "fill_shape_var", None) and self.fill_shape_var.get():
                fill_rgb = self._hex2rgb(self.custom_fill_color or self.draw_color)
                draw.rectangle([x0,y0,x1,y1], fill=(*fill_rgb, 255), outline=col_rgba, width=lw)
            else:
                draw.rectangle([x0,y0,x1,y1], outline=col_rgba, width=lw)

        elif t == "ellipse":
            x0,y0 = min(isx,ix),min(isy,iy)
            x1,y1 = max(isx,ix),max(isy,iy)
            if getattr(self, "fill_shape_var", None) and self.fill_shape_var.get():
                fill_rgb = self._hex2rgb(self.custom_fill_color or self.draw_color)
                draw.ellipse([x0,y0,x1,y1], fill=(*fill_rgb, 255), outline=col_rgba, width=lw)
            else:
                draw.ellipse([x0,y0,x1,y1], outline=col_rgba, width=lw)

        elif t == "highlight":
            x0,y0 = min(isx,ix),min(isy,iy)
            x1,y1 = max(isx,ix),max(isy,iy)
            overlay = Image.new("RGBA", self.edit_img.size, (0,0,0,0))
            ov_draw = ImageDraw.Draw(overlay)
            ov_draw.rectangle([x0,y0,x1,y1], fill=(r,g,b,100))
            self.edit_img = Image.alpha_composite(self.edit_img, overlay)

        elif t == "mosaic":
            x0,y0 = min(isx,ix),min(isy,iy)
            x1,y1 = max(isx,ix),max(isy,iy)
            iw,ih = self.edit_img.size
            x0,y0 = max(0,x0),max(0,y0)
            x1,y1 = min(iw,x1),min(ih,y1)
            if x1-x0 > 4 and y1-y0 > 4:
                region = self.edit_img.crop((x0,y0,x1,y1))
                small  = region.resize((max(1,(x1-x0)//10), max(1,(y1-y0)//10)), Image.BOX)
                blurred = small.resize((x1-x0, y1-y0), Image.NEAREST)
                self.edit_img.paste(blurred, (x0,y0))

        self._refresh_canvas()

    # ══════════════════════════════════════════════
    #  도구 보조 메서드
    # ══════════════════════════════════════════════
    def _draw_arrow(self, draw, x1,y1,x2,y2, color, lw):
        draw.line([x1,y1,x2,y2], fill=color, width=lw)
        angle = math.atan2(y2-y1, x2-x1)
        size  = max(12, lw*4)
        spread = math.pi/6
        for side in (spread, -spread):
            ex = x2 - size * math.cos(angle - side)
            ey = y2 - size * math.sin(angle - side)
            draw.line([x2,y2,int(ex),int(ey)], fill=color, width=lw)

    def _do_text(self, x, y):
        text = simpledialog.askstring("텍스트 입력", "입력할 텍스트:", parent=self)
        if not text:
            return
        self._push_undo()
        draw = ImageDraw.Draw(self.edit_img)
        font_size = self._fsize_var.get()
        self.font_size = font_size
        pil_font = self._get_pil_font(self.font_family, font_size)
        r,g,b = self._hex2rgb(self.draw_color)
        draw.text((x, y), text, fill=(r,g,b,255), font=pil_font)
        self._refresh_canvas()

    def _get_pil_font(self, family, size):
        font_map = {
            "Malgun Gothic": "malgun.ttf",
            "Arial":         "arial.ttf",
            "Consolas":      "consola.ttf",
            "Courier New":   "cour.ttf",
            "Times New Roman":"times.ttf",
            "Calibri":       "calibri.ttf",
        }
        fname = font_map.get(family, "arial.ttf")
        path  = os.path.join("C:/Windows/Fonts", fname)
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()

    def _hex2rgb(self, hex_color):
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2],16) for i in (0,2,4))

    # ══════════════════════════════════════════════
    #  Undo / Redo
    # ══════════════════════════════════════════════
    def _push_undo(self):
        self.undo_stack.append(self.edit_img.copy())
        if len(self.undo_stack) > self.MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.edit_img.copy())
            self.edit_img = self.undo_stack.pop()
            self._fit_and_refresh()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.edit_img.copy())
            self.edit_img = self.redo_stack.pop()
            self._fit_and_refresh()

    # ══════════════════════════════════════════════
    #  변환 (회전/반전)
    # ══════════════════════════════════════════════
    def rotate(self, deg):
        self._push_undo()
        self.edit_img = self.edit_img.rotate(deg, expand=True)
        self._fit_and_refresh()

    def flip(self, mode):
        self._push_undo()
        if mode == "h":
            self.edit_img = ImageOps.mirror(self.edit_img)
        else:
            self.edit_img = ImageOps.flip(self.edit_img)
        self._fit_and_refresh()

    # ══════════════════════════════════════════════
    #  저장 / 클립보드
    # ══════════════════════════════════════════════
    def _final_img(self):
        return self.edit_img.convert("RGB")

    def save(self):
        img = self._final_img()
        ext = os.path.splitext(self.filepath)[1].lower()
        if ext in (".jpg",".jpeg"):
            img.save(self.filepath, quality=95)
        else:
            img.save(self.filepath)
        self.app.update_thumbnails()
        self.title(f"편집기 — {os.path.basename(self.filepath)} ✓")

    def save_as(self):
        ft = [("PNG","*.png"),("JPEG","*.jpg *.jpeg"),("모든 파일","*.*")]
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=ft,
            initialdir=os.path.dirname(self.filepath), parent=self)
        if path:
            img = self._final_img()
            ext = os.path.splitext(path)[1].lower()
            img.save(path, quality=95) if ext in (".jpg",".jpeg") else img.save(path)
            self.filepath = path
            self.title(f"편집기 — {os.path.basename(path)} ✓")

    def copy_to_clipboard(self):
        self.app.copy_image_to_clipboard(self._final_img())

class MainApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DS Capture v1.01")
        
        try:
            dpi = self.root.winfo_fpixels('1i')
            self.scale_factor = dpi / 96.0
        except:
            self.scale_factor = 1.0
            
        win_w = int(580 * self.scale_factor)
        win_h = int(480 * self.scale_factor)
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.minsize(win_w, win_h)
        self.root.attributes("-topmost", True)
        self.sw, self.sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        
        # [수정] 기본값 설정 및 설정 불러오기
        self.save_dir = BASE_DIR
        self.save_format = "png"
        self.shortcuts = {"fixed": None, "drag": None, "full": None}
        self.recent_captures = []
        self.thumbnail_images = []
        self.close_action = "tray"
        
        self.load_config() # 시작할 때 저장된 설정 읽기

        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)

        # UI 구성
        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self.left_frame = tk.Frame(self.main_container)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_w = int(220 * self.scale_factor)
        self.right_frame = tk.Frame(self.main_container, width=right_w, bg="#1e272e")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, expand=False)
        self.right_frame.pack_propagate(False)

        # 우측 프레임 (최근 캡처 목록)
        tk.Label(self.right_frame, text="최근 캡처 목록", bg="#1e272e", fg="#00d2d3", font=("Malgun Gothic", 10, "bold")).pack(pady=(20, 10))
        
        bot_f = tk.Frame(self.right_frame, bg="#1e272e")
        bot_f.pack(side=tk.BOTTOM, fill=tk.X, pady=10, padx=10)
        
        tk.Label(bot_f, text="※ 더블클릭 시 이미지 수정", bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 8)).pack(pady=(0, 8))
        
        tk.Button(bot_f, text="모두 지우기", command=self.clear_all_recent, bg="#e84118", fg="white", font=("Malgun Gothic", 9, "bold"), pady=4, cursor="hand2", bd=0).pack(fill=tk.X, pady=(0, 4))
        tk.Button(bot_f, text="다른 폴더에 모두 저장", command=self.save_all_recent_as, bg="#0097e6", fg="white", font=("Malgun Gothic", 9, "bold"), pady=4, cursor="hand2", bd=0).pack(fill=tk.X)

        self.canvas_recent = tk.Canvas(self.right_frame, bg="#1e272e", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.right_frame, orient="vertical", command=self.canvas_recent.yview)
        self.scrollable_frame = tk.Frame(self.canvas_recent, bg="#1e272e")
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas_recent.configure(scrollregion=self.canvas_recent.bbox("all")))
        self.canvas_recent.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=int(200 * self.scale_factor))
        self.canvas_recent.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side="right", fill="y")
        self.canvas_recent.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.root.bind_all("<MouseWheel>", lambda e: self.canvas_recent.yview_scroll(int(-1*(e.delta/120)), "units"))

        tk.Label(self.left_frame, text="CAPTURE MODES", fg="#00d2d3", font=("Arial", 10, "bold")).pack(pady=(25, 10))

        cap_style = {"bg": "#2f3542", "fg": "white", "font": ("Malgun Gothic", 10, "bold"), "pady": 12, "activebackground": "#57606f", "cursor": "hand2", "bd": 0}
        opt_style = {"bg": "#4b6584", "fg": "white", "font": ("Malgun Gothic", 10, "bold"), "pady": 10, "activebackground": "#778ca3", "cursor": "hand2", "bd": 0}

        btn_con = tk.Frame(self.left_frame); btn_con.pack(fill=tk.BOTH, expand=True, padx=40)
        
        tk.Button(btn_con, text="지정크기 캡처", command=self.open_box, **cap_style).pack(fill=tk.X, pady=(0, 2))
        
        f = tk.Frame(btn_con); f.pack(pady=(0, 15))
        self.ent_w = tk.Entry(f, width=5, justify='center', font=("Arial", 10), bd=2, relief="groove")
        self.ent_w.insert(0, getattr(self, 'saved_box_width', "800")); self.ent_w.pack(side=tk.LEFT, padx=3)
        tk.Label(f, text="×", font=("Arial", 10, "bold"), fg="#a4b0be").pack(side=tk.LEFT)
        self.ent_h = tk.Entry(f, width=5, justify='center', font=("Arial", 10), bd=2, relief="groove")
        self.ent_h.insert(0, getattr(self, 'saved_box_height', "600")); self.ent_h.pack(side=tk.LEFT, padx=3)
        
        tk.Button(btn_con, text="자유 드래그 캡처", command=self.start_drag, **cap_style).pack(fill=tk.X, pady=(0, 2))
        
        self.drag_ratio_var = tk.StringVar(value=getattr(self, 'saved_drag_ratio', "4:3 비율"))
        ratio_f = tk.Frame(btn_con)
        ratio_f.pack(fill=tk.X, pady=(0, 15))
        self.btn_ratio_43 = tk.Button(ratio_f, text="4:3 비율", command=lambda: self.set_ratio("4:3 비율"), bg="#00d2d3", fg="white", font=("Arial", 9, "bold"), pady=6, bd=0, width=12, cursor="hand2")
        self.btn_ratio_43.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_ratio_169 = tk.Button(ratio_f, text="16:9 비율", command=lambda: self.set_ratio("16:9 비율"), bg="#4b6584", fg="white", font=("Arial", 9, "bold"), pady=6, bd=0, width=12, cursor="hand2")
        self.btn_ratio_169.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))
        self.update_ratio_buttons()
        
        tk.Button(btn_con, text="전체 화면 캡처", command=self.full_capture, **cap_style).pack(fill=tk.X, pady=(0, 15))
        
        tk.Button(btn_con, text="⚙️ 환경설정 (SETTINGS)", command=self.open_settings_window, **opt_style).pack(fill=tk.X, pady=(20, 0))

        # 불러온 단축키 즉시 적용
        self.apply_shortcuts()
        
        # 최근 캡처 목록 화면에 렌더링
        self.update_thumbnails()

        self.create_tray_icon()

    def open_settings_window(self):
        if hasattr(self, 'settings_win') and self.settings_win.winfo_exists():
            self.settings_win.focus_force()
            return
            
        pop = tk.Toplevel(self.root)
        self.settings_win = pop
        pop.title("환경설정 (Settings)")
        pop.geometry(f"{int(400 * self.scale_factor)}x{int(580 * self.scale_factor)}")
        pop.attributes("-topmost", True)
        pop.config(bg="#1e272e")
        
        btn_con = tk.Frame(pop, bg="#1e272e")
        btn_con.pack(fill=tk.BOTH, expand=True, padx=int(30 * self.scale_factor), pady=int(20 * self.scale_factor))
        
        opt_style = {"bg": "#4b6584", "fg": "white", "font": ("Malgun Gothic", 10, "bold"), "pady": int(10 * self.scale_factor), "activebackground": "#778ca3", "cursor": "hand2", "bd": 0}

        tk.Button(btn_con, text="단축키 지정", command=self.popup_shortcut_settings, **opt_style).pack(fill=tk.X, pady=(0, 4))
        tk.Button(btn_con, text="저장 위치 지정", command=self.set_save_location, **opt_style).pack(fill=tk.X, pady=(0, 4))
        tk.Button(btn_con, text="저장 폴더 열기", command=self.open_save_folder, **opt_style).pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(btn_con, text="저장 파일 형식", bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 9, "bold")).pack(pady=(15, 0), anchor="w")
        fmt_f = tk.Frame(btn_con, bg="#1e272e"); fmt_f.pack(fill=tk.X, pady=(5, 0))
        self.btn_png = tk.Button(fmt_f, text="PNG", command=lambda: self.set_format("png"), bg="#00d2d3", fg="white", font=("Arial", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_png.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_jpg = tk.Button(fmt_f, text="JPG", command=lambda: self.set_format("jpg"), bg="#4b6584", fg="white", font=("Arial", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_jpg.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        tk.Label(btn_con, text="닫기 버튼 동작", bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 9, "bold")).pack(pady=(15, 0), anchor="w")
        close_f = tk.Frame(btn_con, bg="#1e272e"); close_f.pack(fill=tk.X, pady=(5, 0))
        self.btn_close_tray = tk.Button(close_f, text="트레이로", command=lambda: self.set_close_action("tray"), bg="#00d2d3", fg="white", font=("Arial", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_close_tray.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_close_exit = tk.Button(close_f, text="완전 종료", command=lambda: self.set_close_action("exit"), bg="#4b6584", fg="white", font=("Arial", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_close_exit.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        tk.Label(btn_con, text="윈도우 시작 시 자동실행", bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 9, "bold")).pack(pady=(15, 0), anchor="w")
        startup_f = tk.Frame(btn_con, bg="#1e272e"); startup_f.pack(fill=tk.X, pady=(5, 0))
        self.btn_startup_on = tk.Button(startup_f, text="자동실행 켬", command=lambda: self.set_startup(True), bg="#4b6584", fg="white", font=("Arial", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_startup_on.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_startup_off = tk.Button(startup_f, text="자동실행 끔", command=lambda: self.set_startup(False), bg="#00d2d3", fg="white", font=("Arial", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_startup_off.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        self.update_format_buttons()
        self.update_close_action_buttons()
        self.update_startup_buttons()

    # --- [신규] 설정 저장/불러오기 로직 ---
    def save_config(self):
        """현재 설정을 JSON 파일로 저장합니다."""
        config = {
            "save_dir": self.save_dir,
            "save_format": self.save_format,
            "shortcuts": self.shortcuts,
            "close_action": getattr(self, 'close_action', 'tray'),
            "box_width": self.ent_w.get() if hasattr(self, 'ent_w') else getattr(self, 'saved_box_width', "800"),
            "box_height": self.ent_h.get() if hasattr(self, 'ent_h') else getattr(self, 'saved_box_height', "600"),
            "drag_ratio": self.drag_ratio_var.get() if hasattr(self, 'drag_ratio_var') else getattr(self, 'saved_drag_ratio', "4:3 비율"),
            "recent_captures": self.recent_captures[:10]
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

    def load_config(self):
        """저장된 JSON 파일에서 설정을 읽어옵니다."""
        self.saved_box_width = "800"
        self.saved_box_height = "600"
        self.saved_drag_ratio = "4:3 비율"
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.save_dir = config.get("save_dir", self.save_dir)
                    self.save_format = config.get("save_format", self.save_format)
                    self.shortcuts = config.get("shortcuts", self.shortcuts)
                    self.saved_box_width = config.get("box_width", "800")
                    self.saved_box_height = config.get("box_height", "600")
                    self.saved_drag_ratio = config.get("drag_ratio", "4:3 비율")
                    self.close_action = config.get("close_action", "tray")
                    
                    saved_recent = config.get("recent_captures", [])
                    self.recent_captures = [fp for fp in saved_recent if os.path.exists(fp)][:10]
            except:
                pass

    def apply_shortcuts(self):
        """저장된 단축키 문자열을 실제 keyboard 훅으로 등록합니다."""
        keyboard.unhook_all()
        for mode, hk_str in self.shortcuts.items():
            if not hk_str: continue
            try:
                if mode == "fixed": keyboard.add_hotkey(hk_str, self.open_box)
                elif mode == "drag": keyboard.add_hotkey(hk_str, self.start_drag)
                elif mode == "full": keyboard.add_hotkey(hk_str, self.full_capture)
            except: pass

    # --- 기존 기능들 수정 (저장 로직 포함) ---
    def set_format(self, fmt):
        self.save_format = fmt
        self.update_format_buttons()
        self.save_config()

    def update_format_buttons(self):
        if hasattr(self, 'btn_png') and self.btn_png.winfo_exists():
            self.btn_png.config(bg="#00d2d3" if self.save_format=="png" else "#4b6584")
            self.btn_jpg.config(bg="#00d2d3" if self.save_format=="jpg" else "#4b6584")

    def set_ratio(self, ratio):
        self.drag_ratio_var.set(ratio)
        self.update_ratio_buttons()

    def update_ratio_buttons(self):
        if hasattr(self, 'btn_ratio_43') and hasattr(self, 'btn_ratio_169'):
            self.btn_ratio_43.config(bg="#00d2d3" if self.drag_ratio_var.get()=="4:3 비율" else "#4b6584")
            self.btn_ratio_169.config(bg="#00d2d3" if self.drag_ratio_var.get()=="16:9 비율" else "#4b6584")

    def set_close_action(self, action):
        self.close_action = action
        self.update_close_action_buttons()
        self.save_config()

    def update_close_action_buttons(self):
        if hasattr(self, 'btn_close_tray') and self.btn_close_tray.winfo_exists():
            self.btn_close_tray.config(bg="#00d2d3" if getattr(self, 'close_action', 'tray') == "tray" else "#4b6584")
            self.btn_close_exit.config(bg="#00d2d3" if getattr(self, 'close_action', 'tray') == "exit" else "#4b6584")

    def check_run_on_startup(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "DSCapture")
            winreg.CloseKey(key)
            path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
            return value == f'"{path}"'
        except Exception:
            return False

    def set_startup(self, enable):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if enable:
                path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
                winreg.SetValueEx(key, "DSCapture", 0, winreg.REG_SZ, f'"{path}"')
            else:
                try:
                    winreg.DeleteValue(key, "DSCapture")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Startup reg error: {e}")
        self.update_startup_buttons()

    def update_startup_buttons(self):
        if hasattr(self, 'btn_startup_on') and self.btn_startup_on.winfo_exists():
            is_on = self.check_run_on_startup()
            self.btn_startup_on.config(bg="#00d2d3" if is_on else "#4b6584")
            self.btn_startup_off.config(bg="#00d2d3" if not is_on else "#4b6584")

    def set_save_location(self):
        d = filedialog.askdirectory(initialdir=self.save_dir)
        if d: 
            self.save_dir = d
            self.save_config() # 경로 변경 시 저장

    def popup_shortcut_settings(self):
        pop = tk.Toplevel(self.root)
        pop.title("단축키 설정")
        pop.geometry("420x350")
        pop.attributes("-topmost", True)
        modes = [("지정크기 캡처", "fixed"), ("자유 드래그", "drag"), ("전체화면 캡처", "full")]
        keys_list = [chr(i) for i in range(65, 91)] + [str(i) for i in range(10)] + [f"F{i}" for i in range(1, 13)]
        results = {}
        
        for label, key in modes:
            frame = tk.LabelFrame(pop, text=label, padx=10, pady=10)
            frame.pack(fill=tk.X, padx=20, pady=5)
            
            # 저장된 단축키 파싱해서 체크박스 초기값 설정
            saved_hk = self.shortcuts.get(key, "") or ""
            res = {
                "ctrl": tk.BooleanVar(value="ctrl" in saved_hk),
                "alt": tk.BooleanVar(value="alt" in saved_hk),
                "shift": tk.BooleanVar(value="shift" in saved_hk),
                "key": tk.StringVar(value=saved_hk.split("+")[-1].upper() if saved_hk else "None")
            }
            results[key] = res
            
            tk.Checkbutton(frame, text="Ctrl", variable=res["ctrl"]).pack(side=tk.LEFT)
            tk.Checkbutton(frame, text="Alt", variable=res["alt"]).pack(side=tk.LEFT)
            tk.Checkbutton(frame, text="Shift", variable=res["shift"]).pack(side=tk.LEFT)
            cb = ttk.Combobox(frame, textvariable=res["key"], values=keys_list, width=7, state="readonly")
            cb.pack(side=tk.RIGHT, padx=5)

        def save_shortcuts_action():
            for mode, config in results.items():
                k = config["key"].get()
                if k == "None":
                    self.shortcuts[mode] = None
                    continue
                hk = [m for m in ["ctrl", "alt", "shift"] if config[m].get()] + [k.lower()]
                self.shortcuts[mode] = "+".join(hk)
            
            self.apply_shortcuts() # 즉시 적용
            self.save_config()    # 파일에 저장
            pop.destroy()
            
        tk.Button(pop, text="단축키 적용 및 저장", command=save_shortcuts_action, bg="#2f3542", fg="white", pady=10).pack(fill=tk.X, padx=40, pady=20)

    # --- 트레이 아이콘 및 기타 로직 (기존과 동일) ---
    def create_tray_icon(self):
        icon_img = Image.new('RGB', (64, 64), color=(47, 53, 66))
        d = ImageDraw.Draw(icon_img)
        d.rectangle([16, 16, 48, 48], outline=(0, 210, 211), width=4)
        menu = pystray.Menu(
            pystray.MenuItem('Open', self.show_window),
            pystray.MenuItem('Open Folder', self.open_save_folder),
            pystray.MenuItem('Exit', self.quit_app)
        )
        self.tray_icon = pystray.Icon("CapturePro", icon_img, "Capture Pro", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def open_save_folder(self, icon=None, item=None):
        try: os.startfile(self.save_dir)
        except: pass

    def on_close_window(self):
        if getattr(self, 'close_action', 'tray') == 'exit':
            self.quit_app()
        else:
            self.withdraw_window()

    def withdraw_window(self):
        self.save_config()
        self.root.withdraw()

    def show_window(self, icon=None, item=None):
        self.root.deiconify()
        self.root.attributes("-topmost", True)

    def quit_app(self, icon=None, item=None):
        self.save_config()
        try:
            self.tray_icon.stop()
        except:
            pass
        try:
            keyboard.unhook_all()
        except:
            pass
        os._exit(0)

    def copy_image_to_clipboard(self, img):
        output = io.BytesIO()
        img.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        if user32.OpenClipboard(0):
            try:
                user32.EmptyClipboard()
                h_mem = kernel32.GlobalAlloc(0x0042, len(data))
                if h_mem:
                    p_mem = kernel32.GlobalLock(h_mem)
                    if p_mem:
                        ctypes.memmove(p_mem, data, len(data))
                        kernel32.GlobalUnlock(h_mem)
                        user32.SetClipboardData(8, h_mem)
            finally: user32.CloseClipboard()

    def open_box(self):
        self.save_config()
        self.root.withdraw()
        ResizableBox(self.root, int(self.ent_w.get()), int(self.ent_h.get()), self.execute_capture)

    def start_drag(self):
        self.root.withdraw()
        self.root.update()
        time.sleep(0.2)
        
        screen_img = ImageGrab.grab(bbox=(0, 0, self.sw, self.sh))
        enhancer = ImageEnhance.Brightness(screen_img)
        dark_img = enhancer.enhance(0.8)
        
        ov = tk.Toplevel()
        ov.attributes("-fullscreen", True, "-topmost", True)
        cv = tk.Canvas(ov, highlightthickness=0, cursor="none"); cv.pack(fill=tk.BOTH, expand=True)
        
        ov.dark_photo = ImageTk.PhotoImage(dark_img)
        cv.create_image(0, 0, image=ov.dark_photo, anchor="nw")
        
        ov.bind("<Escape>", lambda e: (ov.destroy(), self.show_window()))
        ov.focus_force()
        rd = {"id": None, "tid": None, "tbg": None, "x": 0, "y": 0, "vline": None, "hline": None, "clear_img": None}
        rd["clear_img"] = cv.create_image(0, 0, anchor="nw")
        
        cv.create_rectangle(self.sw // 2 - 320, 15, self.sw // 2 + 320, 45, fill="#1e1e1e", outline="")
        cv.create_text(self.sw // 2, 30, text="[Shift] 비율 고정    [Ctrl] 중앙 기준 드래그    [Ctrl+Shift] 중앙 기준+비율 고정    [ESC] 취소", fill="#f1c40f", font=("Malgun Gothic", 10, "bold"), anchor="center")
        
        rd["vline"] = cv.create_line(-10, 0, -10, self.sh, fill="red", width=1.5)
        rd["hline"] = cv.create_line(0, -10, self.sw, -10, fill="red", width=1.5)
        
        def on_hover(e):
            cv.coords(rd["vline"], e.x, 0, e.x, self.sh)
            cv.coords(rd["hline"], 0, e.y, self.sw, e.y)
        
        def on_p(e):
            rd["x"], rd["y"] = e.x, e.y
            rd["id"] = cv.create_rectangle(e.x, e.y, e.x, e.y, outline="red", width=3)
            rd["tbg"] = cv.create_rectangle(0, 0, 0, 0, fill="black", outline="")
            rd["tid"] = cv.create_text(e.x, e.y-10, text="0 x 0", fill="white", font=("Malgun Gothic", 11, "bold"), anchor="sw")
        def get_rect(e):
            cx, cy = e.x, e.y
            x0, y0 = rd["x"], rd["y"]
            is_shift = (e.state & 0x0001) != 0
            is_ctrl = (e.state & 0x0004) != 0
            
            dx, dy = cx - x0, cy - y0
            
            if is_shift and abs(dx) > 0:
                ratio_str = self.drag_ratio_var.get()
                target_ratio = 4.0 / 3.0 if ratio_str == "4:3 비율" else 16.0 / 9.0
                h = abs(dx) / target_ratio
                dy = h if dy >= 0 else -h

            if is_ctrl:
                max_abs_dx = min(x0, self.sw - x0)
                max_abs_dy = min(y0, self.sh - y0)
            else:
                max_abs_dx = self.sw - x0 if dx > 0 else x0
                max_abs_dy = self.sh - y0 if dy > 0 else y0
                
            abs_dx, abs_dy = abs(dx), abs(dy)
            
            if abs_dx > max_abs_dx and abs_dx > 0:
                scale = max_abs_dx / abs_dx
                dx *= scale; dy *= scale
                abs_dx, abs_dy = abs(dx), abs(dy)
                
            if abs_dy > max_abs_dy and abs_dy > 0:
                scale = max_abs_dy / abs_dy
                dx *= scale; dy *= scale
            
            if is_ctrl:
                x1, y1 = x0 - dx, y0 - dy
                x2, y2 = x0 + dx, y0 + dy
            else:
                x1, y1 = x0, y0
                x2, y2 = x0 + dx, y0 + dy
                
            return x1, y1, x2, y2

        def on_m(e):
            x1, y1, x2, y2 = get_rect(e)
            
            cv.coords(rd["id"], x1, y1, x2, y2)
            cv.coords(rd["vline"], e.x, 0, e.x, self.sh)
            cv.coords(rd["hline"], 0, e.y, self.sw, e.y)
            
            w, h = int(abs(x2 - x1)), int(abs(y2 - y1))
            tx, ty = min(x1, x2), min(y1, y2) - 5
            cv.itemconfig(rd["tid"], text=f" {w} x {h} ")
            b = cv.bbox(rd["tid"]); cv.coords(rd["tbg"], b[0]-2, b[1]-2, b[2]+2, b[3]+2); cv.coords(rd["tid"], tx, ty)
            
            cx_min, cy_min = min(x1, x2), min(y1, y2)
            if w > 0 and h > 0:
                cropped = screen_img.crop((cx_min, cy_min, cx_min + w, cy_min + h))
                ov.active_photo = ImageTk.PhotoImage(cropped)
                cv.itemconfig(rd["clear_img"], image=ov.active_photo)
                cv.coords(rd["clear_img"], cx_min, cy_min)

        def on_r(e):
            x1, y1, x2, y2 = get_rect(e)
            cx_min, cy_min = min(x1, x2), min(y1, y2)
            cx_max, cy_max = max(x1, x2), max(y1, y2)
            ov.destroy(); self.execute_capture(cx_min, cy_min, cx_max, cy_max); self.show_window()
        cv.bind("<Motion>", on_hover); cv.bind("<Button-1>", on_p); cv.bind("<B1-Motion>", on_m); cv.bind("<ButtonRelease-1>", on_r)

    def full_capture(self):
        self.root.withdraw(); self.root.update(); time.sleep(0.3)
        self.execute_capture(0, 0, self.sw, self.sh)
        self.show_window()

    def on_thumbnail_dblclick(self, filepath):
        """썸네일 더블클릭 시 이미지 편집기 오픈"""
        if os.path.exists(filepath):
            ImageEditor(self.root, filepath, self)

    def _show_thumbnail_menu(self, event, filepath):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="이미지 수정", command=lambda: self.on_thumbnail_dblclick(filepath))
        menu.add_separator()
        menu.add_command(label="다른 이름으로 저장", command=lambda: self._save_thumbnail_as(filepath))
        menu.add_command(label="삭제", command=lambda: self._delete_thumbnail(filepath))
        menu.tk_popup(event.x_root, event.y_root)

    def _save_thumbnail_as(self, filepath):
        if not os.path.exists(filepath): return
        ext = os.path.splitext(filepath)[1].lower()
        ft = [("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg"), ("모든 파일", "*.*")]
        save_path = filedialog.asksaveasfilename(
            defaultextension=".png" if ext == ".png" else ".jpg",
            filetypes=ft,
            initialfile=os.path.basename(filepath),
            initialdir=os.path.dirname(filepath),
            parent=self.root)
        if save_path:
            import shutil
            try:
                shutil.copy2(filepath, save_path)
            except Exception as e:
                print(f"Error saving file: {e}")

    def _delete_thumbnail(self, filepath):
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Error deleting file: {e}")
        if filepath in self.recent_captures:
            self.recent_captures.remove(filepath)
        self.update_thumbnails()

    def update_thumbnails(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.thumbnail_images.clear()

        for filepath in self.recent_captures:
            if not os.path.exists(filepath): continue
            try:
                img = Image.open(filepath)
                img.thumbnail((160, 120))
                photo = ImageTk.PhotoImage(img)
                self.thumbnail_images.append(photo)

                thumb_frame = tk.Frame(self.scrollable_frame, bg="#2f3542", bd=0)
                thumb_frame.pack(pady=5, padx=5, fill=tk.X)

                lbl = tk.Label(thumb_frame, image=photo, bg="#2f3542", cursor="hand2")
                lbl.pack(pady=(5, 0))
                lbl.bind("<Double-Button-1>", lambda e, path=filepath: self.on_thumbnail_dblclick(path))
                lbl.bind("<Button-3>", lambda e, path=filepath: self._show_thumbnail_menu(e, path))
                
                name_lbl = tk.Label(thumb_frame, text=os.path.basename(filepath), bg="#2f3542", fg="white", font=("Arial", 8))
                name_lbl.pack(pady=2)
                name_lbl.bind("<Button-3>", lambda e, path=filepath: self._show_thumbnail_menu(e, path))
            except Exception as e:
                print(f"Error loading thumbnail: {e}")

    def execute_capture(self, x1, y1, x2, y2):
        l, t, r, b = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        if r - l < 5 or b - t < 5: return
        time_str = time.strftime('%Y-%m-%d_%H%M%S')
        filename = f"{time_str}_capture.{self.save_format}"
        filepath = os.path.join(self.save_dir, filename)
        try:
            img = ImageGrab.grab(bbox=(l, t, r, b), all_screens=True)
            self.copy_image_to_clipboard(img)
            if self.save_format == "jpg": img.convert("RGB").save(filepath, quality=95)
            else: img.save(filepath)
            
            self.recent_captures.insert(0, filepath)
            if len(self.recent_captures) > 10:
                self.recent_captures.pop()
            
            self.root.after(100, self.update_thumbnails)
        except: pass

    def clear_all_recent(self):
        if not self.recent_captures: return
        from tkinter import messagebox
        if not messagebox.askyesno("모두 지우기", "정말로 최근 캡처 목록의 모든 이미지를 삭제하시겠습니까?\n(실제 파일도 모두 삭제됩니다)"):
            return
        for fp in self.recent_captures:
            if os.path.exists(fp):
                try: os.remove(fp)
                except Exception: pass
        self.recent_captures.clear()
        self.update_thumbnails()

    def save_all_recent_as(self):
        if not self.recent_captures: return
        d = filedialog.askdirectory(title="저장할 폴더 선택")
        if not d: return
        import shutil
        for fp in self.recent_captures:
            if os.path.exists(fp):
                try: shutil.copy2(fp, os.path.join(d, os.path.basename(fp)))
                except Exception: pass

if __name__ == "__main__":
    MainApp().root.mainloop()