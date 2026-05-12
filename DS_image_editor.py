import tkinter as tk
from tkinter import filedialog, ttk, colorchooser, simpledialog, messagebox
import os
import sys
import math
import ctypes
from ctypes import wintypes
import io
import time
from PIL import Image, ImageDraw, ImageTk, ImageOps, ImageFont, ImageEnhance, ImageFilter

# --- [윈도우 API 및 초기 설정] ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

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

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', BASE_DIR)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def set_window_icon(window):
    try:
        ico_path = get_resource_path("icon/DS_capture.ico")
        if os.path.exists(ico_path):
            window.iconbitmap(ico_path)
    except:
        pass

def copy_image_to_clipboard(img):
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
        finally:
            user32.CloseClipboard()

class ImageEditor(tk.Toplevel):
    MAX_UNDO = 10
    PALETTE = ["#FF0000", "#FF8C00", "#FFFF00", "#008000", 
               "#0000FF", "#800080", "#FFFFFF", "#000000"]

    def __init__(self, parent, filepath):
        super().__init__(parent)
        self.withdraw()
        self.filepath = filepath
        self.attributes("-topmost", False)
        self.title(f"편집기 — {os.path.basename(filepath)}")
        set_window_icon(self)

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        target_w = int(sw * 0.75)
        target_h = int(target_w * 9 / 16)
        x = (sw - target_w) // 2
        y = (sh - target_h) // 2
        self.geometry(f"{target_w}x{target_h}+{x}+{y}")

        raw = Image.open(filepath)
        self.edit_img = raw.convert("RGBA")
        self.undo_stack = []
        self.redo_stack = []

        self.current_tool = "pen"
        self.draw_color   = "#FF0000"
        self.custom_fill_color = "#FF0000"
        self.line_width   = 5
        self.font_family  = "Malgun Gothic"
        self.font_size    = 20
        self.fill_shape_var = tk.BooleanVar(value=False)

        self._sx = self._sy = 0
        self._temp_items = []
        self._pen_pts    = []
        self.scale       = 1.0
        self._tk_img     = None
        self._tool_btns  = {}
        
        self.prev_lw = self.line_width
        self.prev_color = self.draw_color

        self._build_ui()
        self.after(50, self._fit_and_refresh)
        self._bind_events()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.deiconify()
        self.focus_force()

    def _build_ui(self):
        top_area = tk.Frame(self, bg="#1e272e")
        top_area.pack(fill=tk.X)
        
        bs = dict(bg="#485460", fg="white", font=("Malgun Gothic", 9, "bold"),
                  bd=0, padx=12, pady=6, cursor="hand2",
                  activebackground="#0fbcf9", activeforeground="white")

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
        
        self._size_lbl = tk.Label(row1, text="", bg="#1e272e", fg="#00d8d6", font=("Malgun Gothic", 10, "bold"))
        self._size_lbl.pack(side=tk.RIGHT, padx=10)

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

        row3 = tk.Frame(top_area, bg="#1e272e", pady=10, padx=12)
        row3.pack(fill=tk.X)
        
        def create_palette(parent, callback):
            for c in self.PALETTE:
                tk.Button(parent, bg=c, width=2, height=1, bd=1, relief="solid", cursor="hand2", 
                          command=lambda col=c: callback(col)).pack(side=tk.LEFT, padx=2)
            tk.Button(parent, text="⊕", bg="#485460", fg="white", bd=0, cursor="hand2", font=("Malgun Gothic",10, "bold"), 
                      command=self._pick_color if callback == self._set_color else self._pick_fill_color, padx=8).pack(side=tk.LEFT, padx=5)

        tk.Label(row3, text="선 색상:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0,6))
        create_palette(row3, self._set_color)
        self._color_ind = tk.Label(row3, bg=self.draw_color, width=3, height=1, relief="solid", bd=1)
        self._color_ind.pack(side=tk.LEFT, padx=3)

        tk.Frame(row3, bg="#808e9b", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=4)
        tk.Label(row3, text="선 두께:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0,6))
        self._width_var = tk.IntVar(value=self.line_width)
        tk.Spinbox(row3, from_=1, to=100, textvariable=self._width_var, width=4, font=("Malgun Gothic", 10), 
                   command=lambda: setattr(self,"line_width",self._width_var.get())).pack(side=tk.LEFT)
                   
        tk.Frame(row3, bg="#808e9b", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=4)
        tk.Checkbutton(row3, text="채우기", variable=self.fill_shape_var, bg="#1e272e", fg="#d2dae2", 
                       selectcolor="#2f3640", activebackground="#1e272e", activeforeground="white",
                       font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(5,6))
        create_palette(row3, self._set_fill_color)
        self._fill_color_ind = tk.Label(row3, bg=self.custom_fill_color, width=3, height=1, relief="solid", bd=1)
        self._fill_color_ind.pack(side=tk.LEFT, padx=3)

        tk.Frame(row3, bg="#808e9b", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=4)
        tk.Label(row3, text="글꼴:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0,6))
        self._font_var = tk.StringVar(value=self.font_family)
        ttk.Combobox(row3, textvariable=self._font_var, values=["Malgun Gothic", "Consolas", "Impact"], state="readonly", width=10, font=("Malgun Gothic", 9)).pack(side=tk.LEFT, padx=2)
        self._font_var.trace_add("write", lambda *a: setattr(self,"font_family",self._font_var.get()))

        tk.Label(row3, text="크기:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(8,4))
        self._fsize_var = tk.IntVar(value=self.font_size)
        tk.Spinbox(row3, from_=8, to=120, textvariable=self._fsize_var, width=3, font=("Malgun Gothic", 10), 
                   command=lambda: setattr(self,"font_size",self._fsize_var.get())).pack(side=tk.LEFT)

        self.canvas = tk.Canvas(self, bg="#2f3640", cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def _select_tool(self, name):
        prev_t = self.current_tool
        self.current_tool = name
        for n, b in self._tool_btns.items():
            b.config(bg="#0fbcf9" if n == name else "#718093")
        if name == "highlight":
            if prev_t != "highlight":
                self.prev_lw = self.line_width
                self.prev_color = self.draw_color
            self.draw_color = "#FFFF00"
            self.line_width = 25
            self._color_ind.config(bg=self.draw_color)
            self._width_var.set(25)
        elif prev_t == "highlight":
            self.line_width = self.prev_lw
            self.draw_color = self.prev_color
            self._color_ind.config(bg=self.draw_color)
            self._width_var.set(self.line_width)

    def _set_color(self, color):
        self.draw_color = color
        self._color_ind.config(bg=color)

    def _pick_color(self):
        c = colorchooser.askcolor(color=self.draw_color, parent=self)[1]
        if c: self._set_color(c)

    def _pick_fill_color(self):
        c = colorchooser.askcolor(color=self.custom_fill_color or self.draw_color, parent=self)[1]
        if c: self._set_fill_color(c)

    def _set_fill_color(self, color):
        self.custom_fill_color = color
        self._fill_color_ind.config(bg=color)
        self.fill_shape_var.set(True)

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
        try: r_filter = Image.Resampling.BILINEAR
        except AttributeError: r_filter = Image.BILINEAR
        disp = self.edit_img.convert("RGB").resize((dw, dh), r_filter)
        self._tk_img = ImageTk.PhotoImage(disp)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

    def _c2i(self, cx, cy):
        return int(cx / self.scale), int(cy / self.scale)

    def _get_norm_rect(self, x1, y1, x2, y2):
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    def _is_shift_pressed(self, event):
        return (event.state & 0x0001) or (ctypes.windll.user32.GetKeyState(0x10) & 0x8000)

    def _bind_events(self):
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",        self._on_drag)
        self.canvas.bind("<ButtonRelease-1>",  self._on_release)
        self.bind("<Control-z>",               lambda e: self.undo())
        self.bind("<Control-Z>",               lambda e: self.undo())
        self.bind("<Control-y>",               lambda e: self.redo())
        self.bind("<Control-Y>",               lambda e: self.redo())
        self.bind("<Escape>",                  lambda e: self.on_close())
        self.bind("<Configure>",               self._on_configure)

    def _on_configure(self, event):
        if event.widget == self:
            if hasattr(self, '_cfg_job') and self._cfg_job is not None:
                self.after_cancel(self._cfg_job)
            self._cfg_job = self.after(50, self._fit_and_refresh)

    def _on_press(self, event):
        self._sx, self._sy = event.x, event.y
        self._pen_pts = [(event.x, event.y)]
        for item in self._temp_items: self.canvas.delete(item)
        self._temp_items = []

    def _on_drag(self, event):
        if self.current_tool not in ["pen", "highlight"]:
            for item in self._temp_items: self.canvas.delete(item)
            self._temp_items = []
        x, y = event.x, event.y
        sx, sy = self._sx, self._sy
        col = self.draw_color
        lw  = max(1, int(self._width_var.get() * self.scale))
        t   = self.current_tool

        if t in ["pen", "highlight"]:
            is_shift = self._is_shift_pressed(event)
            if t == "highlight":
                y = sy
                self._pen_pts = [(sx, sy), (x, y)]
                self._temp_items.append(self.canvas.create_line(sx, sy, x, y, fill=col, width=lw, capstyle=tk.ROUND))
            elif is_shift:
                if abs(x - sx) > abs(y - sy): y = sy
                else: x = sx
                self._pen_pts = [(sx, sy), (x, y)]
                self._temp_items.append(self.canvas.create_line(sx, sy, x, y, fill=col, width=lw, capstyle=tk.ROUND))
            else:
                self._pen_pts.append((x, y))
                pts = self._pen_pts
                if len(pts) >= 2:
                    self._temp_items.append(self.canvas.create_line(*pts[-2], *pts[-1], fill=col, width=lw, capstyle=tk.ROUND, joinstyle=tk.ROUND))
        elif t == "line": self._temp_items.append(self.canvas.create_line(sx,sy,x,y,fill=col,width=lw))
        elif t == "arrow": self._temp_items.append(self.canvas.create_line(sx,sy,x,y,fill=col,width=lw, arrow=tk.LAST, arrowshape=(16,20,6)))
        elif t == "rect":
            x0, y0, x1, y1 = self._get_norm_rect(sx, sy, x, y)
            if self.fill_shape_var.get():
                fill_c = self.custom_fill_color or col
                self._temp_items.append(self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill_c, outline=col, width=lw))
            else: self._temp_items.append(self.canvas.create_rectangle(x0, y0, x1, y1, outline=col, width=lw))
        elif t == "ellipse":
            x0, y0, x1, y1 = self._get_norm_rect(sx, sy, x, y)
            if self.fill_shape_var.get():
                fill_c = self.custom_fill_color or col
                self._temp_items.append(self.canvas.create_oval(x0, y0, x1, y1, fill=fill_c, outline=col, width=lw))
            else: self._temp_items.append(self.canvas.create_oval(x0, y0, x1, y1, outline=col, width=lw))
        elif t in ("mosaic","crop","text"):
            x0, y0, x1, y1 = self._get_norm_rect(sx, sy, x, y)
            self._temp_items.append(self.canvas.create_rectangle(x0, y0, x1, y1, outline="#00FF00", width=2, dash=(6,4)))

    def _on_release(self, event):
        for item in self._temp_items: self.canvas.delete(item)
        self._temp_items = []
        x, y   = event.x, event.y
        sx, sy = self._sx, self._sy
        ix, iy   = self._c2i(x,  y)
        isx, isy = self._c2i(sx, sy)
        t = self.current_tool
        if t == "text": self._do_text(isx, isy); return
        if t == "crop":
            x0,y0 = min(isx,ix), min(isy,iy); x1,y1 = max(isx,ix), max(isy,iy)
            iw, ih = self.edit_img.size
            x0,y0 = max(0,x0), max(0,y0); x1,y1 = min(iw,x1), min(ih,y1)
            if x1-x0 > 5 and y1-y0 > 5:
                self._push_undo()
                self.edit_img = self.edit_img.crop((x0,y0,x1,y1))
                self._fit_and_refresh()
            return
        self._push_undo()
        draw = ImageDraw.Draw(self.edit_img)
        r,g,b = self._hex2rgb(self.draw_color); col_rgba = (r,g,b,255); lw = self.line_width
        if t == "pen":
            if self._is_shift_pressed(event):
                if abs(x - sx) > abs(y - sy): y = sy
                else: x = sx
                self._pen_pts = [(sx, sy), (x, y)]
            pts = [self._c2i(px,py) for px,py in self._pen_pts]
            if len(pts) >= 2: draw.line(pts, fill=col_rgba, width=lw, joint="curve")
            elif len(pts) == 1:
                r2 = max(1, lw//2); px,py = pts[0]
                draw.ellipse([px-r2,py-r2,px+r2,py+r2], fill=col_rgba)
        elif t == "line": draw.line([isx,isy,ix,iy], fill=col_rgba, width=lw)
        elif t == "arrow": self._draw_arrow(draw, isx,isy,ix,iy, col_rgba, lw)
        elif t in ["rect", "ellipse"]:
            x0, y0, x1, y1 = self._get_norm_rect(isx, isy, ix, iy)
            is_fill = self.fill_shape_var.get()
            fill_rgb = self._hex2rgb(self.custom_fill_color or self.draw_color) if is_fill else None
            if t == "rect":
                if is_fill: draw.rectangle([x0, y0, x1, y1], fill=(*fill_rgb, 255), outline=col_rgba, width=lw)
                else: draw.rectangle([x0, y0, x1, y1], outline=col_rgba, width=lw)
            else:
                if is_fill: draw.ellipse([x0, y0, x1, y1], fill=(*fill_rgb, 255), outline=col_rgba, width=lw)
                else: draw.ellipse([x0, y0, x1, y1], outline=col_rgba, width=lw)
        elif t == "highlight":
            y = sy; pts = [self._c2i(px, py) for px, py in [(sx, sy), (x, y)]]
            overlay = Image.new("RGBA", self.edit_img.size, (0,0,0,0)); ov_draw = ImageDraw.Draw(overlay)
            ov_draw.line(pts, fill=(r,g,b,50), width=lw, joint="round")
            overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.4))
            self.edit_img = Image.alpha_composite(self.edit_img, overlay)
        elif t == "mosaic":
            x0, y0, x1, y1 = self._get_norm_rect(isx, isy, ix, iy)
            iw, ih = self.edit_img.size; x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(iw, x1), min(ih, y1)
            if x1 - x0 > 4 and y1 - y0 > 4:
                region = self.edit_img.crop((x0, y0, x1, y1))
                small = region.resize((max(1, (x1 - x0) // 10), max(1, (y1 - y0) // 10)), Image.BOX)
                blurred = small.resize((x1 - x0, y1 - y0), Image.NEAREST)
                self.edit_img.paste(blurred, (x0, y0))
        self._refresh_canvas()

    def _draw_arrow(self, draw, x1,y1,x2,y2, color, lw):
        draw.line([x1,y1,x2,y2], fill=color, width=lw)
        angle = math.atan2(y2-y1, x2-x1); size = max(12, lw*4); spread = math.pi/6
        for side in (spread, -spread):
            ex = x2 - size * math.cos(angle - side); ey = y2 - size * math.sin(angle - side)
            draw.line([x2,y2,int(ex),int(ey)], fill=color, width=lw)

    def _do_text(self, x, y):
        text = simpledialog.askstring("텍스트 입력", "입력할 텍스트:", parent=self)
        if not text: return
        self._push_undo()
        draw = ImageDraw.Draw(self.edit_img)
        font_size = self._fsize_var.get(); self.font_size = font_size
        pil_font = self._get_pil_font(self.font_family, font_size)
        r,g,b = self._hex2rgb(self.draw_color)
        draw.text((x, y), text, fill=(r,g,b,255), font=pil_font)
        self._refresh_canvas()

    def _get_pil_font(self, family, size):
        font_map = {"Malgun Gothic": "malgun.ttf", "Consolas": "consola.ttf", "Courier New": "cour.ttf", "Times New Roman":"times.ttf", "Calibri": "calibri.ttf"}
        fname = font_map.get(family, "arial.ttf"); path = os.path.join("C:/Windows/Fonts", fname)
        try: return ImageFont.truetype(path, size)
        except: return ImageFont.load_default()

    def _hex2rgb(self, hex_color):
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2],16) for i in (0,2,4))

    def _push_undo(self):
        self.undo_stack.append(self.edit_img.copy())
        if len(self.undo_stack) > self.MAX_UNDO: self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack: self.redo_stack.append(self.edit_img.copy()); self.edit_img = self.undo_stack.pop(); self._fit_and_refresh()

    def redo(self):
        if self.redo_stack: self.undo_stack.append(self.edit_img.copy()); self.edit_img = self.redo_stack.pop(); self._fit_and_refresh()

    def rotate(self, deg):
        self._push_undo(); self.edit_img = self.edit_img.rotate(deg, expand=True); self._fit_and_refresh()

    def flip(self, mode):
        self._push_undo()
        if mode == "h": self.edit_img = ImageOps.mirror(self.edit_img)
        else: self.edit_img = ImageOps.flip(self.edit_img)
        self._fit_and_refresh()

    def _final_img(self): return self.edit_img.convert("RGB")

    def save(self):
        img = self._final_img(); ext = os.path.splitext(self.filepath)[1].lower()
        if ext in (".jpg",".jpeg"): img.save(self.filepath, quality=95)
        else: img.save(self.filepath)
        self.title(f"편집기 — {os.path.basename(self.filepath)} ✓")

    def save_as(self):
        ft = [("PNG","*.png"),("JPEG","*.jpg *.jpeg"),("모든 파일","*.*")]
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=ft, initialdir=os.path.dirname(self.filepath), parent=self)
        if path:
            img = self._final_img(); ext = os.path.splitext(path)[1].lower()
            img.save(path, quality=95) if ext in (".jpg",".jpeg") else img.save(path)
            self.filepath = path; self.title(f"편집기 — {os.path.basename(path)} ✓")

    def copy_to_clipboard(self):
        copy_image_to_clipboard(self._final_img())

    def on_close(self):
        # 명시적 메모리 해제
        self.edit_img = None
        self.undo_stack.clear()
        self.redo_stack.clear()
        import gc
        gc.collect()
        self.master.destroy()

def run_editor(img_path):
    if not os.path.exists(img_path):
        return
    root = tk.Tk()
    root.withdraw()
    editor = ImageEditor(root, img_path)
    root.mainloop()

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        run_editor(sys.argv[1])
