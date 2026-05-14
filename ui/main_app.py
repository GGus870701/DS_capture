import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import sys
import time
import json
import threading
import subprocess
import io
import winreg
import pythoncom
import win32gui
import win32com.client
import keyboard
import pystray
from PIL import Image, ImageGrab, ImageTk, ImageEnhance
from core.utils import (
    BUILD_VERSION, BUILD_DATE, BUILD_TIME, BASE_DIR, 
    CONFIG_FILE, LICENSE_DIR, get_resource_path, set_window_icon
)
from ui.resizable_box import ResizableBox

# Windows API for clipboard
import ctypes
from ctypes import wintypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

class MainApp:
    def __init__(self, license_data=None):
        self.license_data = license_data or {}
        self.root = tk.Tk()
        set_window_icon(self.root)
        
        user_info = self.license_data.get('user_name', 'Free User')
        short_ver = ".".join(BUILD_VERSION.split(".")[:2])
        self.root.title(f"DS Capture {short_ver} - [{user_info}]")
        
        self.is_startup = "--startup" in sys.argv
        
        try:
            dpi = self.root.winfo_fpixels('1i')
            self.scale_factor = dpi / 96.0
        except:
            self.scale_factor = 1.0
            
        win_w = int(580 * self.scale_factor)
        win_h = int(480 * self.scale_factor)
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.minsize(win_w, win_h)
        self.root.attributes("-topmost", False)
        self.sw, self.sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        
        self.save_dir = BASE_DIR
        self.save_format = "png"
        self.shortcuts = {"fixed": None, "drag": None, "full": None}
        self.recent_captures = []
        self.thumbnail_images = []
        self.close_action = "tray"
        
        self.load_config()
        self.root.bind("<Escape>", self._on_esc_main)

        if not os.path.exists(CONFIG_FILE):
            self.save_config()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)

        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self.left_frame = tk.Frame(self.main_container)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_w = int(220 * self.scale_factor)
        self.right_frame = tk.Frame(self.main_container, width=right_w, bg="#1e272e")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, expand=False)
        self.right_frame.pack_propagate(False)

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

        tk.Label(self.left_frame, text="CAPTURE MODES", fg="#00d2d3", font=("Malgun Gothic", 10, "bold")).pack(pady=(25, 10))

        cap_style = {"bg": "#2f3542", "fg": "white", "font": ("Malgun Gothic", 10, "bold"), "pady": 12, "activebackground": "#57606f", "cursor": "hand2", "bd": 0}
        opt_style = {"bg": "#4b6584", "fg": "white", "font": ("Malgun Gothic", 10, "bold"), "pady": 10, "activebackground": "#778ca3", "cursor": "hand2", "bd": 0}

        btn_con = tk.Frame(self.left_frame)
        btn_con.pack(fill=tk.BOTH, expand=True, padx=40)
        
        tk.Button(btn_con, text="지정크기 캡처", command=self.open_box, **cap_style).pack(fill=tk.X, pady=(0, 2))
        
        f = tk.Frame(btn_con)
        f.pack(pady=(0, 15))
        self.ent_w = tk.Entry(f, width=5, justify='center', font=("Malgun Gothic", 10), bd=2, relief="groove")
        self.ent_w.insert(0, getattr(self, 'saved_box_width', "800"))
        self.ent_w.pack(side=tk.LEFT, padx=3)
        tk.Label(f, text="×", font=("Malgun Gothic", 10, "bold"), fg="#a4b0be").pack(side=tk.LEFT)
        self.ent_h = tk.Entry(f, width=5, justify='center', font=("Malgun Gothic", 10), bd=2, relief="groove")
        self.ent_h.insert(0, getattr(self, 'saved_box_height', "600"))
        self.ent_h.pack(side=tk.LEFT, padx=3)
        
        tk.Button(btn_con, text="자유 드래그 캡처", command=self.start_drag, **cap_style).pack(fill=tk.X, pady=(0, 2))
        
        self.drag_ratio_var = tk.StringVar(value=getattr(self, 'saved_drag_ratio', "4:3 비율"))
        ratio_f = tk.Frame(btn_con)
        ratio_f.pack(fill=tk.X, pady=(0, 15))
        self.btn_ratio_43 = tk.Button(ratio_f, text="4:3 비율", command=lambda: self.set_ratio("4:3 비율"), bg="#00d2d3", fg="white", font=("Malgun Gothic", 9, "bold"), pady=6, bd=0, width=12, cursor="hand2")
        self.btn_ratio_43.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_ratio_169 = tk.Button(ratio_f, text="16:9 비율", command=lambda: self.set_ratio("16:9 비율"), bg="#4b6584", fg="white", font=("Malgun Gothic", 9, "bold"), pady=6, bd=0, width=12, cursor="hand2")
        self.btn_ratio_169.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))
        self.update_ratio_buttons()
        
        tk.Button(btn_con, text="전체 화면 캡처", command=self.full_capture, **cap_style).pack(fill=tk.X, pady=(0, 15))
        
        tk.Button(btn_con, text="⚙️ 환경설정 (SETTINGS)", command=self.open_settings_window, **opt_style).pack(fill=tk.X, pady=(20, 0))

        self.apply_shortcuts()
        self.update_thumbnails()
        self.create_tray_icon()
        
        if self.is_startup:
            self.root.withdraw()

    def open_settings_window(self):
        if hasattr(self, 'settings_win') and self.settings_win.winfo_exists():
            self.settings_win.focus_force()
            return
            
        pop = tk.Toplevel(self.root)
        self.settings_win = pop
        pop.title("환경설정 (Settings)")
        set_window_icon(pop)
        pop.geometry(f"{int(400 * self.scale_factor)}x{int(460 * self.scale_factor)}")
        pop.attributes("-topmost", False)
        pop.config(bg="#1e272e")
        
        def close_pop(e):
            pop.destroy()
            return "break"
        pop.bind("<Escape>", close_pop)
        pop.focus_force()
        
        btn_con = tk.Frame(pop, bg="#1e272e")
        btn_con.pack(fill=tk.BOTH, expand=True, padx=int(30 * self.scale_factor), pady=(int(20 * self.scale_factor), int(5 * self.scale_factor)))
        
        opt_style = {"bg": "#4b6584", "fg": "white", "font": ("Malgun Gothic", 10, "bold"), "pady": int(10 * self.scale_factor), "activebackground": "#778ca3", "cursor": "hand2", "bd": 0}

        tk.Button(btn_con, text="단축키 지정", command=self.popup_shortcut_settings, **opt_style).pack(fill=tk.X, pady=(0, 4))
        tk.Button(btn_con, text="저장 위치 지정", command=self.set_save_location, **opt_style).pack(fill=tk.X, pady=(0, 4))
        tk.Button(btn_con, text="저장 폴더 열기", command=self.open_save_folder, **opt_style).pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(btn_con, text="저장 파일 형식", bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 9, "bold")).pack(pady=(15, 0), anchor="w")
        fmt_f = tk.Frame(btn_con, bg="#1e272e")
        fmt_f.pack(fill=tk.X, pady=(5, 0))
        self.btn_png = tk.Button(fmt_f, text="PNG", command=lambda: self.set_format("png"), bg="#00d2d3", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_png.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_jpg = tk.Button(fmt_f, text="JPG", command=lambda: self.set_format("jpg"), bg="#4b6584", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_jpg.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        tk.Label(btn_con, text="닫기 버튼 동작", bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 9, "bold")).pack(pady=(15, 0), anchor="w")
        close_f = tk.Frame(btn_con, bg="#1e272e")
        close_f.pack(fill=tk.X, pady=(5, 0))
        self.btn_close_tray = tk.Button(close_f, text="트레이로", command=lambda: self.set_close_action("tray"), bg="#00d2d3", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_close_tray.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_close_exit = tk.Button(close_f, text="완전 종료", command=lambda: self.set_close_action("exit"), bg="#4b6584", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_close_exit.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        tk.Label(btn_con, text="윈도우 시작 시 자동실행", bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 9, "bold")).pack(pady=(15, 0), anchor="w")
        startup_f = tk.Frame(btn_con, bg="#1e272e")
        startup_f.pack(fill=tk.X, pady=(5, 0))
        self.btn_startup_on = tk.Button(startup_f, text="자동실행 켬", command=lambda: self.set_startup(True), bg="#4b6584", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_startup_on.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_startup_off = tk.Button(startup_f, text="자동실행 끔", command=lambda: self.set_startup(False), bg="#00d2d3", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_startup_off.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        tk.Label(pop, text=f"Version {BUILD_VERSION} (Build: {BUILD_DATE})", 
                 bg="#1e272e", fg="#57606f", font=("Malgun Gothic", 8)).pack(side=tk.BOTTOM, pady=10)

        self.update_format_buttons()
        self.update_close_action_buttons()
        self.update_startup_buttons()
        
        tk.Frame(btn_con, height=1, bg="#3d3d3d").pack(fill=tk.X, pady=(25, 10))
        
        info_f = tk.Frame(btn_con, bg="#1e272e")
        info_f.pack(fill=tk.X)
        
        tk.Label(info_f, text=f"Version: {BUILD_VERSION}", bg="#1e272e", fg="#a4b0be", 
                 font=("Malgun Gothic", 8)).pack(side=tk.LEFT)
        tk.Label(info_f, text=f"Build: {BUILD_DATE} {BUILD_TIME}", bg="#1e272e", fg="#a4b0be", 
                 font=("Malgun Gothic", 8)).pack(side=tk.RIGHT)
        
        pop.focus_force()

    def save_config(self):
        try:
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
        except Exception as e:
            messagebox.showerror("저장 오류", f"설정 파일을 저장하는 중 오류가 발생했습니다:\n{str(e)}")

    def load_config(self):
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
            except: pass

    def apply_shortcuts(self):
        keyboard.unhook_all()
        for mode, hk_str in self.shortcuts.items():
            if not hk_str: continue
            try:
                if mode == "fixed": keyboard.add_hotkey(hk_str, self.open_box)
                elif mode == "drag": keyboard.add_hotkey(hk_str, self.start_drag)
                elif mode == "full": keyboard.add_hotkey(hk_str, self.full_capture)
            except: pass
            
        try:
            keyboard.add_hotkey('ctrl+v', self.handle_explorer_paste, suppress=False)
        except: pass

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
            return f'"{path}"' in value
        except: return False

    def set_startup(self, enable):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if enable:
                path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
                winreg.SetValueEx(key, "DSCapture", 0, winreg.REG_SZ, f'"{path}" --startup')
            else:
                try: winreg.DeleteValue(key, "DSCapture")
                except: pass
            winreg.CloseKey(key)
        except: pass
        self.update_startup_buttons()

    def update_startup_buttons(self):
        if hasattr(self, 'btn_startup_on') and self.btn_startup_on.winfo_exists():
            is_on = self.check_run_on_startup()
            self.btn_startup_on.config(bg="#00d2d3" if is_on else "#4b6584")
            self.btn_startup_off.config(bg="#00d2d3" if not is_on else "#4b6584")

    def _on_esc_main(self, event):
        for child in self.root.winfo_children():
            if isinstance(child, tk.Toplevel) and child.winfo_exists() and child.winfo_viewable():
                return "break"
        if event.widget == self.root:
            self.on_close_window()
        return "break"

    def set_save_location(self):
        d = filedialog.askdirectory(initialdir=self.save_dir)
        if d: 
            self.save_dir = d
            self.save_config()

    def popup_shortcut_settings(self):
        pop = tk.Toplevel(self.root)
        pop.title("단축키 설정")
        set_window_icon(pop)
        pop.geometry("420x350")
        modes = [("지정크기 캡처", "fixed"), ("자유 드래그", "drag"), ("전체화면 캡처", "full")]
        keys_list = [chr(i) for i in range(65, 91)] + [str(i) for i in range(10)] + [f"F{i}" for i in range(1, 13)]
        results = {}
        for label, key in modes:
            frame = tk.LabelFrame(pop, text=label, padx=10, pady=10)
            frame.pack(fill=tk.X, padx=20, pady=5)
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
            ttk.Combobox(frame, textvariable=res["key"], values=keys_list, width=7, state="readonly").pack(side=tk.RIGHT, padx=5)

        def save_shortcuts_action():
            for mode, config in results.items():
                k = config["key"].get()
                if k == "None": self.shortcuts[mode] = None; continue
                hk = [m for m in ["ctrl", "alt", "shift"] if config[m].get()] + [k.lower()]
                self.shortcuts[mode] = "+".join(hk)
            self.apply_shortcuts()
            self.save_config()
            pop.destroy()
        tk.Button(pop, text="단축키 적용 및 저장", command=save_shortcuts_action, bg="#2f3542", fg="white", pady=10).pack(fill=tk.X, padx=40, pady=20)
        pop.bind("<Escape>", lambda e: pop.destroy())
        pop.focus_force()

    def create_tray_icon(self):
        try:
            icon_path = get_resource_path("icon/DS_capture.ico")
            if os.path.exists(icon_path):
                raw_img = Image.open(icon_path).convert("RGBA")
                bbox = raw_img.getbbox()
                icon_img = raw_img.crop(bbox).resize((64, 64), Image.LANCZOS) if bbox else raw_img.resize((64, 64), Image.LANCZOS)
            else:
                icon_img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
                from PIL import ImageDraw
                draw = ImageDraw.Draw(icon_img)
                draw.ellipse((2, 2, 62, 62), fill="#f1c40f")
        except:
            icon_img = Image.new('RGB', (64, 64), color=(47, 53, 66))
        menu = pystray.Menu(
            pystray.MenuItem('Open', self.show_window, default=True),
            pystray.MenuItem('Open Folder', self.open_save_folder),
            pystray.MenuItem('Exit', self.quit_app)
        )
        self.tray_icon = pystray.Icon("DSCapture", icon_img, "DS Capture", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def open_save_folder(self, icon=None, item=None):
        try: os.startfile(self.save_dir)
        except: pass

    def get_active_explorer_path(self):
        pythoncom.CoInitialize()
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd: return None
            window_title = win32gui.GetWindowText(hwnd)
            shell = win32com.client.Dispatch("Shell.Application")
            explorer_windows = []
            for window in shell.Windows():
                try:
                    if window.HWND == hwnd: explorer_windows.append(window)
                except: continue
            if not explorer_windows:
                class_name = win32gui.GetClassName(hwnd)
                if class_name in ["Progman", "WorkerW"]:
                    return os.path.join(os.environ["USERPROFILE"], "Desktop")
                return None
            if len(explorer_windows) == 1:
                return explorer_windows[0].Document.Folder.Self.Path
            for window in explorer_windows:
                try:
                    loc_name = getattr(window, "LocationName", "")
                    full_path = window.Document.Folder.Self.Path
                    display_name = window.Document.Folder.Title
                    candidates = [loc_name, full_path, display_name]
                    if any(c == window_title for c in candidates if c): return full_path
                    if any(c and (c in window_title or window_title in c) for c in candidates): return full_path
                except: continue
            return explorer_windows[0].Document.Folder.Self.Path
        except: pass
        finally: pythoncom.CoUninitialize()
        return None

    def generate_filename(self):
        time_str = time.strftime('%Y%m%d_%H%M%S')
        return f"{time_str}_capture.{self.save_format}"

    def handle_explorer_paste(self):
        target_path = self.get_active_explorer_path()
        if not target_path: return
        try:
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                filename = self.generate_filename()
                filepath = os.path.join(target_path, filename)
                if self.save_format == "jpg": img.convert("RGB").save(filepath, quality=95)
                else: img.save(filepath)
        except: pass

    def on_close_window(self):
        if getattr(self, 'close_action', 'tray') == 'exit': self.quit_app()
        else: self.withdraw_window()

    def withdraw_window(self):
        self.save_config()
        self.root.withdraw()

    def show_window(self, icon=None, item=None):
        self.root.deiconify()

    def quit_app(self, icon=None, item=None):
        self.save_config()
        try: self.tray_icon.stop()
        except: pass
        try: keyboard.unhook_all()
        except: pass
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
        dark_img = ImageEnhance.Brightness(screen_img).enhance(0.8)
        ov = tk.Toplevel()
        ov.withdraw()
        set_window_icon(ov)
        ov.attributes("-fullscreen", True, "-topmost", True)
        ov.config(bg="black")
        cv = tk.Canvas(ov, highlightthickness=0, cursor="none", bg="black")
        cv.pack(fill=tk.BOTH, expand=True)
        ov.dark_photo = ImageTk.PhotoImage(dark_img)
        cv.create_image(0, 0, image=ov.dark_photo, anchor="nw")
        ov.bind("<Escape>", lambda e: (ov.destroy(), self.show_window()))
        ov.deiconify()
        ov.focus_force()
        rd = {"id": None, "tid": None, "tbg": None, "x": 0, "y": 0, "vline": None, "hline": None}
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
            cx, cy = e.x, e.y; x0, y0 = rd["x"], rd["y"]
            is_shift, is_ctrl = (e.state & 0x0001) != 0, (e.state & 0x0004) != 0
            dx, dy = cx - x0, cy - y0
            if is_shift and abs(dx) > 0:
                target_ratio = 4.0 / 3.0 if self.drag_ratio_var.get() == "4:3 비율" else 16.0 / 9.0
                h = abs(dx) / target_ratio
                dy = h if dy >= 0 else -h
            if is_ctrl:
                m_dx, m_dy = min(x0, self.sw - x0), min(y0, self.sh - y0)
            else:
                m_dx, m_dy = self.sw - x0 if dx > 0 else x0, self.sh - y0 if dy > 0 else y0
            a_dx, a_dy = abs(dx), abs(dy)
            if a_dx > m_dx and a_dx > 0:
                s = m_dx / a_dx; dx *= s; dy *= s; a_dx, a_dy = abs(dx), abs(dy)
            if a_dy > m_dy and a_dy > 0:
                s = m_dy / a_dy; dx *= s; dy *= s
            return (x0 - dx if is_ctrl else x0), (y0 - dy if is_ctrl else y0), x0 + dx, y0 + dy

        def on_m(e):
            x1, y1, x2, y2 = get_rect(e)
            cv.coords(rd["id"], x1, y1, x2, y2)
            cv.coords(rd["vline"], e.x, 0, e.x, self.sh)
            cv.coords(rd["hline"], 0, e.y, self.sw, e.y)
            w, h = int(abs(x2 - x1)), int(abs(y2 - y1))
            tx, ty = min(x1, x2), min(y1, y2) - 5
            cv.itemconfig(rd["tid"], text=f" {w} x {h} ")
            b = cv.bbox(rd["tid"])
            cv.coords(rd["tbg"], b[0]-2, b[1]-2, b[2]+2, b[3]+2)
            cv.coords(rd["tid"], tx, ty)

        def on_r(e):
            x1, y1, x2, y2 = get_rect(e)
            ov.destroy()
            self.execute_capture(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            self.show_window()
            
        cv.bind("<Motion>", on_hover); cv.bind("<Button-1>", on_p); cv.bind("<B1-Motion>", on_m); cv.bind("<ButtonRelease-1>", on_r)

    def full_capture(self):
        self.root.withdraw(); self.root.update(); time.sleep(0.3)
        self.execute_capture(0, 0, self.sw, self.sh)
        self.show_window()

    def on_thumbnail_dblclick(self, filepath):
        if os.path.exists(filepath):
            try:
                # 썸네일 더블클릭 시 이미지 에디터 모드로 실행 (modules.image_editor 사용)
                if getattr(sys, 'frozen', False):
                    subprocess.Popen([sys.executable, "--editor", filepath])
                else:
                    # 스크립트 모드에서는 main.py --editor filepath
                    subprocess.Popen([sys.executable, sys.argv[0], "--editor", filepath])
                self.root.after(2000, self.update_thumbnails)
            except Exception as e:
                messagebox.showerror("오류", f"편집기를 실행할 수 없습니다: {e}")

    def _show_thumbnail_menu(self, event, filepath):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="이미지 수정", command=lambda: self.on_thumbnail_dblclick(filepath))
        menu.add_separator()
        menu.add_command(label="다른 이름으로 저장", command=lambda: self._save_thumbnail_as(filepath))
        menu.add_command(label="삭제", command=lambda: self._delete_thumbnail(filepath))
        menu.tk_popup(event.x_root, event.y_root)

    def _save_thumbnail_as(self, filepath):
        if not os.path.exists(filepath): return
        save_path = filedialog.asksaveasfilename(defaultextension=".png", initialfile=os.path.basename(filepath), initialdir=os.path.dirname(filepath), parent=self.root)
        if save_path:
            import shutil
            try: shutil.copy2(filepath, save_path)
            except: pass

    def _delete_thumbnail(self, filepath):
        if os.path.exists(filepath):
            try: os.remove(filepath)
            except: pass
        if filepath in self.recent_captures: self.recent_captures.remove(filepath)
        self.update_thumbnails()

    def update_thumbnails(self):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        self.thumbnail_images.clear()
        for filepath in self.recent_captures:
            if not os.path.exists(filepath): continue
            try:
                img = Image.open(filepath); img.thumbnail((160, 120)); photo = ImageTk.PhotoImage(img)
                self.thumbnail_images.append(photo)
                thumb_frame = tk.Frame(self.scrollable_frame, bg="#2f3542", bd=0); thumb_frame.pack(pady=5, padx=5, fill=tk.X)
                lbl = tk.Label(thumb_frame, image=photo, bg="#2f3542", cursor="hand2"); lbl.pack(pady=(5, 0))
                lbl.bind("<Double-Button-1>", lambda e, path=filepath: self.on_thumbnail_dblclick(path))
                lbl.bind("<Button-3>", lambda e, path=filepath: self._show_thumbnail_menu(e, path))
                name_lbl = tk.Label(thumb_frame, text=os.path.basename(filepath), bg="#2f3542", fg="white", font=("Malgun Gothic", 8)); name_lbl.pack(pady=2)
                name_lbl.bind("<Button-3>", lambda e, path=filepath: self._show_thumbnail_menu(e, path))
            except: pass

    def execute_capture(self, x1, y1, x2, y2):
        l, t, r, b = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        if r - l < 5 or b - t < 5: return
        filename = self.generate_filename(); filepath = os.path.join(self.save_dir, filename)
        try:
            img = ImageGrab.grab(bbox=(l, t, r, b), all_screens=True)
            self.copy_image_to_clipboard(img)
            if self.save_format == "jpg": img.convert("RGB").save(filepath, quality=95)
            else: img.save(filepath)
            self.recent_captures.insert(0, filepath)
            if len(self.recent_captures) > 10: self.recent_captures.pop()
            self.root.after(100, self.update_thumbnails)
        except: pass

    def clear_all_recent(self):
        if not self.recent_captures: return
        if not messagebox.askyesno("모두 지우기", "최근 캡처 목록의 이미지를 모두 삭제하시겠습니까?"): return
        for fp in self.recent_captures:
            if os.path.exists(fp):
                try: os.remove(fp)
                except: pass
        self.recent_captures.clear(); self.update_thumbnails()

    def save_all_recent_as(self):
        if not self.recent_captures: return
        d = filedialog.askdirectory(title="저장할 폴더 선택")
        if not d: return
        import shutil
        for fp in self.recent_captures:
            if os.path.exists(fp):
                try: shutil.copy2(fp, os.path.join(d, os.path.basename(fp)))
                except: pass
