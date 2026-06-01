import tkinter as tk
import time
from core.utils import set_window_icon

class ResizableBox(tk.Toplevel):
    def __init__(self, parent, width, height, on_capture):
        super().__init__(parent)
        self.on_capture = on_capture
        set_window_icon(self)
        self.top_bar_h = 40    
        import ctypes
        user32 = ctypes.windll.user32
        self.v_x = user32.GetSystemMetrics(76)
        self.v_y = user32.GetSystemMetrics(77)
        self.sw = user32.GetSystemMetrics(78)
        self.sh = user32.GetSystemMetrics(79)
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
                                   command=self.close_box, bd=0, font=("Malgun Gothic", 14, "bold"), 
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
        self.bind("<Escape>", lambda e: self._on_esc_box())
        self.bind("<Return>", lambda e: self.trigger_capture())
        self.catcher.bind("<Return>", lambda e: self.trigger_capture())
        self.catcher.bind("<Escape>", lambda e: self._on_esc_box())
        self.bind("<Configure>", self.sync_ui)
        
        self.is_capturing = False

    def close_box(self):
        if hasattr(self, 'catcher') and self.catcher.winfo_exists():
            self.catcher.destroy()
        self.master.deiconify()
        self.destroy()

    def _on_esc_box(self):
        self.close_box()
        return "break"

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
        x = max(self.v_x, min(self.v_x + self.sw - self.winfo_width(), self.wx + dx))
        y = max(self.v_y, min(self.v_y + self.sh - self.winfo_height(), self.wy + dy))
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
        new_w = max(250, min(self.v_x + self.sw - self.winfo_x(), self.sww + dx))
        if event.state & 0x0001:
            ratio = self.sww / (self.shh - self.top_bar_h)
            new_h = int((new_w / ratio) + self.top_bar_h)
            if new_h > self.v_y + self.sh - self.winfo_y():
                new_h = self.v_y + self.sh - self.winfo_y()
                new_w = int((new_h - self.top_bar_h) * ratio)
        else:
            new_h = max(150, min(self.v_y + self.sh - self.winfo_y(), self.shh + dy))
        self.geometry(f"{new_w}x{new_h}")

    def trigger_capture(self):
        if self.is_capturing: return
        self.is_capturing = True
        
        w, h = self.winfo_width(), self.winfo_height() - self.top_bar_h
        x = self.winfo_x()
        y = self.winfo_y() + self.top_bar_h if self.bar_position == "top" else self.winfo_y()
        
        if hasattr(self, 'catcher') and self.catcher.winfo_exists():
            self.catcher.withdraw()
            
        self.withdraw()
        self.update()
        time.sleep(0.2)
        
        try:
            self.on_capture(x, y, x + w, y + h)
        finally:
            self.deiconify()
            if hasattr(self, 'catcher') and self.catcher.winfo_exists():
                self.catcher.deiconify()
            
            self.focus_force()
            if hasattr(self, 'catcher') and self.catcher.winfo_exists():
                self.catcher.focus_force()
            self.after(500, self._reset_capture_flag)

    def _reset_capture_flag(self):
        self.is_capturing = False
