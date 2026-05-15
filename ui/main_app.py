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
import win32clipboard
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
        self.root.withdraw() # 초기화 중 빈 하얀 창 방지
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
            
        win_w = int(510 * self.scale_factor)
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

        # 저장된 위치가 있으면 적용, 없으면 중앙 배치
        if hasattr(self, 'saved_win_x') and self.saved_win_x is not None:
            self.root.geometry(f"+{self.saved_win_x}+{self.saved_win_y}")
        else:
            # 기본 중앙 배치 (기존 로직 유지 가능 또는 직접 계산)
            pos_x = (self.sw - win_w) // 2
            pos_y = (self.sh - win_h) // 2
            self.root.geometry(f"+{pos_x}+{pos_y}")
        self.root.bind("<Escape>", self._on_esc_main)

        if not os.path.exists(CONFIG_FILE):
            self.save_config()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)

        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self.left_frame = tk.Frame(self.main_container, width=int(290 * self.scale_factor))
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.left_frame.pack_propagate(False)

        right_w = int(220 * self.scale_factor)
        self.right_frame = tk.Frame(self.main_container, width=right_w, bg="#1e272e")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.right_frame.pack_propagate(False)

        tk.Label(self.right_frame, text="최근 캡처 및 수정 목록\n(최대 100개)", bg="#1e272e", fg="#00d2d3", font=("Malgun Gothic", 10, "bold")).pack(pady=(20, 10))
        
        bot_f = tk.Frame(self.right_frame, bg="#1e272e")
        bot_f.pack(side=tk.BOTTOM, fill=tk.X, pady=10, padx=10)
        
        tk.Label(bot_f, text="※ 더블클릭 시 이미지 수정", bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 8)).pack(pady=(0, 8))
        
        tk.Button(bot_f, text="모두 지우기", command=self.clear_all_recent, bg="#e84118", fg="white", font=("Malgun Gothic", 9, "bold"), pady=4, cursor="hand2", bd=0).pack(fill=tk.X, pady=(0, 4))
        tk.Button(bot_f, text="다른 폴더에 모두 저장", command=self.save_all_recent_as, bg="#0097e6", fg="white", font=("Malgun Gothic", 9, "bold"), pady=4, cursor="hand2", bd=0).pack(fill=tk.X)

        self.canvas_recent = tk.Canvas(self.right_frame, bg="#1e272e", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.right_frame, orient="vertical", command=self.canvas_recent.yview)
        self.scrollable_frame = tk.Frame(self.canvas_recent, bg="#1e272e")
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas_recent.configure(scrollregion=self.canvas_recent.bbox("all")))
        self.canvas_window = self.canvas_recent.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas_recent.bind("<Configure>", lambda e: self.canvas_recent.itemconfig(self.canvas_window, width=e.width))
        self.canvas_recent.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side="right", fill="y")
        self.canvas_recent.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.root.bind_all("<MouseWheel>", lambda e: self.canvas_recent.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # 스크롤 감시 및 리사이즈 대응 지연 로딩 연결
        self.canvas_recent.bind("<Configure>", self.on_canvas_resize)
        self.canvas_recent.config(yscrollcommand=self.on_canvas_scroll)
        self.loaded_count = 0
        self.items_per_page = 10
        self._resize_timer = None

        tk.Label(self.left_frame, text="CAPTURE MODES", fg="#00d2d3", font=("Malgun Gothic", 10, "bold")).pack(pady=(25, 10))

        cap_style = {"bg": "#2f3542", "fg": "white", "font": ("Malgun Gothic", 10, "bold"), "pady": 12, "activebackground": "#57606f", "cursor": "hand2", "bd": 0}
        opt_style = {"bg": "#4b6584", "fg": "white", "font": ("Malgun Gothic", 10, "bold"), "pady": 10, "activebackground": "#778ca3", "cursor": "hand2", "bd": 0}

        btn_con = tk.Frame(self.left_frame)
        btn_con.pack(fill=tk.BOTH, expand=True, padx=15)
        
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

        # 하단 로고 및 카피라이트 문구 통합 배치
        copyright_f = tk.Frame(self.left_frame)
        copyright_f.pack(side=tk.BOTTOM, fill=tk.X, pady=20)
        
        # 로고 영역 (왼쪽)
        try:
            from core.utils import get_resource_path
            logo_path = get_resource_path("DASAN Technology Safety logo.png")
            if os.path.exists(logo_path):
                logo_img = Image.open(logo_path)
                target_w = int(35 * self.scale_factor)
                w, h = logo_img.size
                ratio = target_w / w
                target_h = int(h * ratio)
                logo_img = logo_img.resize((target_w, target_h), Image.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(logo_img)
                
                logo_lbl = tk.Label(copyright_f, image=self.logo_photo)
                logo_lbl.pack(side=tk.LEFT, padx=(20, 10))
        except: pass

        # 텍스트 영역 (오른쪽)
        text_f = tk.Frame(copyright_f)
        text_f.pack(side=tk.LEFT, anchor="w")
        tk.Label(text_f, text="© 2026 DASAN Technology Safety", fg="#95a5a6", font=("Malgun Gothic", 8, "bold"), anchor="w").pack(fill=tk.X)
        tk.Label(text_f, text="All Rights Reserved.", fg="#bdc3c7", font=("Malgun Gothic", 7), anchor="w").pack(fill=tk.X)

        self.apply_shortcuts()
        self.update_thumbnails()
        self.create_tray_icon()
        
        if not self.is_startup:
            self.root.deiconify()

        # 창이 포커스를 받을 때 목록 갱신 (리소스 절약 및 에디터 저장 결과 반영)
        self.root.bind("<FocusIn>", lambda e: self.refresh_recent_list())

    def refresh_recent_list(self):
        """저장 폴더를 스캔하여 목록을 최신화함 (수동 또는 이벤트 발생 시 호출)"""
        try:
            if not os.path.exists(self.save_dir): return
            
            # 폴더 내 이미지 파일들 (시간순 정렬)
            files = [os.path.join(self.save_dir, f) for f in os.listdir(self.save_dir) 
                     if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
            files.sort(key=os.path.getmtime, reverse=True)
            
            # 상위 100개 추출
            new_recent = files[:100]
            
            # 변경사항이 있을 때만 UI 갱신
            if new_recent != self.recent_captures:
                self.recent_captures = new_recent
                self.update_thumbnails()
                self.save_config()
        except:
            pass

    def open_settings_window(self):
        if hasattr(self, 'settings_win') and self.settings_win.winfo_exists():
            self.settings_win.focus_force()
            return
            
        pop = tk.Toplevel(self.root)
        self.settings_win = pop
        pop.title("환경설정 (Settings)")
        set_window_icon(pop)
        # 메인 윈도우 중앙에 배치하기 위한 좌표 계산
        pop_w = int(400 * self.scale_factor)
        pop_h = int(540 * self.scale_factor)
        
        # 메인 윈도우의 현재 위치와 크기 가져오기
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_w = self.root.winfo_width()
        main_h = self.root.winfo_height()
        
        # 기본적으로 메인 윈도우의 중앙에 배치
        pos_x = main_x + (main_w - pop_w) // 2
        pos_y = main_y + (main_h - pop_h) // 2
        
        # 단, 메인 윈도우가 화면 최상단에 있어 중앙 정렬 시 상단이 잘릴 경우 상단 정렬 방식 적용
        if pos_y < 0:
            pos_y = main_y + int(30 * self.scale_factor)
            if pos_y < 0: pos_y = 0 # 최종 보정
        
        pop.geometry(f"{pop_w}x{pop_h}+{pos_x}+{pos_y}")
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
        
        # 저장 폴더 열기 버튼 (동적 텍스트 적용)
        self.btn_open_folder = tk.Button(btn_con, text="저장 폴더 열기", command=self.open_save_folder, **opt_style)
        self.btn_open_folder.pack(fill=tk.X, pady=(0, 4))
        self.update_open_folder_button_text()
        
        tk.Label(btn_con, text="저장 파일 형식", bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 9, "bold")).pack(pady=(15, 0), anchor="w")
        fmt_f = tk.Frame(btn_con, bg="#1e272e")
        fmt_f.pack(fill=tk.X, pady=(5, 0))
        self.btn_png = tk.Button(fmt_f, text="PNG", command=lambda: self.set_format("png"), bg="#00d2d3", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_png.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_jpg = tk.Button(fmt_f, text="JPG", command=lambda: self.set_format("jpg"), bg="#4b6584", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_jpg.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        tk.Label(btn_con, text="저장 방식", bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 9, "bold")).pack(pady=(15, 0), anchor="w")
        mode_f = tk.Frame(btn_con, bg="#1e272e")
        mode_f.pack(fill=tk.X, pady=(5, 0))
        self.btn_save_both = tk.Button(mode_f, text="파일저장+클립보드", command=lambda: self.set_save_mode("both"), bg="#00d2d3", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_save_both.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_save_clip = tk.Button(mode_f, text="클립보드", command=lambda: self.set_save_mode("clipboard"), bg="#4b6584", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_save_clip.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        tk.Label(btn_con, text="닫기 버튼 동작", bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 9, "bold")).pack(pady=(15, 0), anchor="w")
        close_f = tk.Frame(btn_con, bg="#1e272e")
        close_f.pack(fill=tk.X, pady=(5, 0))
        self.btn_close_tray = tk.Button(close_f, text="트레이로", command=lambda: self.set_close_action("tray"), bg="#00d2d3", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_close_tray.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_close_exit = tk.Button(close_f, text="프로그램 종료", command=lambda: self.set_close_action("exit"), bg="#4b6584", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_close_exit.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        tk.Label(btn_con, text="윈도우 시작 시 자동실행", bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 9, "bold")).pack(pady=(15, 0), anchor="w")
        startup_f = tk.Frame(btn_con, bg="#1e272e")
        startup_f.pack(fill=tk.X, pady=(5, 0))
        self.btn_startup_on = tk.Button(startup_f, text="자동실행 켬", command=lambda: self.set_startup(True), bg="#4b6584", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_startup_on.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_startup_off = tk.Button(startup_f, text="자동실행 끔", command=lambda: self.set_startup(False), bg="#00d2d3", fg="white", font=("Malgun Gothic", 9, "bold"), pady=8, bd=0, width=12, cursor="hand2")
        self.btn_startup_off.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        self.update_format_buttons()
        self.update_save_mode_buttons()
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
                "save_mode": getattr(self, 'save_mode', 'both'),
                "recent_captures": self.recent_captures[:100],
                "win_x": self.root.winfo_x(),
                "win_y": self.root.winfo_y()
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
                    self.save_mode = config.get("save_mode", "both")
                    self.saved_win_x = config.get("win_x")
                    self.saved_win_y = config.get("win_y")
                    
                    saved_recent = config.get("recent_captures", [])
                    self.recent_captures = [fp for fp in saved_recent if os.path.exists(fp)][:100]
            except: pass

    def apply_shortcuts(self):
        try:
            keyboard.unhook_all()
        except: pass

        for mode, hk_str in self.shortcuts.items():
            if not hk_str: continue
            try:
                if mode == "fixed": keyboard.add_hotkey(hk_str, self.open_box)
                elif mode == "drag": keyboard.add_hotkey(hk_str, self.start_drag)
                elif mode == "full": keyboard.add_hotkey(hk_str, self.full_capture)
            except: pass
            
        # 탐색기 이미지 붙여넣기 (Ctrl+Shift+V) 등록
        try:
            keyboard.add_hotkey('ctrl+shift+v', self.handle_explorer_paste, suppress=False)
        except: pass

    def set_save_mode(self, mode):
        self.save_mode = mode
        self.update_save_mode_buttons()
        self.save_config()

    def update_save_mode_buttons(self):
        if hasattr(self, 'btn_save_both') and self.btn_save_both.winfo_exists():
            self.btn_save_both.config(bg="#00d2d3" if getattr(self, 'save_mode', 'both') == "both" else "#4b6584")
            self.btn_save_clip.config(bg="#00d2d3" if getattr(self, 'save_mode', 'both') == "clipboard" else "#4b6584")

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
        # 팝업창(Toplevel)이 떠 있는 경우에는 해당 창이 닫히도록 'break'만 반환
        for child in self.root.winfo_children():
            if isinstance(child, tk.Toplevel) and child.winfo_exists() and child.winfo_viewable():
                return "break"
        # 메인 윈도우 자체는 Esc로 닫히지 않도록 수정
        return "break"

    def set_save_location(self):
        # 환경설정 창이 있으면 부모로 지정하여 포커스 문제 방지
        parent = self.settings_win if hasattr(self, 'settings_win') and self.settings_win.winfo_exists() else self.root
        d = filedialog.askdirectory(initialdir=self.save_dir, parent=parent)
        if d: 
            self.save_dir = d
            self.update_open_folder_button_text() # 환경설정 창 내 버튼 텍스트 갱신
            self.refresh_recent_list() # 새로운 경로의 파일들로 썸네일 즉시 갱신
            self.save_config()
        
        # 다이얼로그가 닫힌 후 다시 환경설정 창을 최상단으로 올림
        if hasattr(self, 'settings_win') and self.settings_win.winfo_exists():
            self.settings_win.lift()
            self.settings_win.focus_force()

    def update_open_folder_button_text(self):
        """환경설정 창의 폴더 열기 버튼 텍스트를 현재 전체 경로(축약형)로 업데이트"""
        if hasattr(self, 'btn_open_folder') and self.btn_open_folder.winfo_exists():
            full_path = self.save_dir
            short_path = self.shorten_path(full_path, max_len=35)
            self.btn_open_folder.config(text=f"저장 위치 [{short_path}] 열기")

    def shorten_path(self, path, max_len=40):
        r"""드라이브명, 최초 폴더, 최종 폴더를 우선 노출 (예: C:\First\...\Final)"""
        if not path: return ""
        if len(path) <= max_len:
            return path
        
        normalized_path = path.replace('/', os.sep).replace('\\', os.sep)
        parts = [p for p in normalized_path.split(os.sep) if p]
        
        if len(parts) <= 2:
            return path[-max_len:] if len(path) > max_len else path
            
        drive = parts[0] + os.sep
        first_folder = parts[1]
        final_folder = parts[-1]
        
        # 기본 형태: 드라이브\첫폴더\...\마지막폴더
        if len(parts) > 3:
            res = f"{drive}{first_folder}{os.sep}...{os.sep}{final_folder}"
        else:
            # 폴더가 3개뿐인 경우 (C:\A\B)
            res = f"{drive}{first_folder}{os.sep}{final_folder}"
            
        # 만약 이 결과도 너무 길면 드라이브와 마지막 폴더 위주로 더 줄임
        if len(res) > max_len:
            available = max_len - len(drive) - 5
            return f"{drive}...{os.sep}{final_folder[-available:]}" if available > 5 else f"{drive}...{final_folder[-10:]}"
            
        return res

    def popup_shortcut_settings(self):
        pop = tk.Toplevel(self.root)
        pop.title("단축키 설정")
        set_window_icon(pop)
        pop.geometry("420x350")
        modes = [("지정크기 캡처", "fixed"), ("자유 드래그", "drag"), ("전체화면 캡처", "full")]
        keys_list = [chr(i) for i in range(65, 91)] + [str(i) for i in range(10)] + [f"F{i}" for i in range(1, 13)]
        results = {}
        def reset_single_shortcut(config):
            config["ctrl"].set(False)
            config["alt"].set(False)
            config["shift"].set(False)
            config["key"].set("None")

        def update_modifier_dependency(res, shift_cb, ent):
            """Ctrl 또는 Alt가 체크되어야만 Shift 및 키 입력이 가능하도록 제어"""
            if res["ctrl"].get() or res["alt"].get():
                shift_cb.config(state=tk.NORMAL)
                ent.config(state=tk.NORMAL, bg="white")
            else:
                res["shift"].set(False)
                res["key"].set("None")
                shift_cb.config(state=tk.DISABLED)
                ent.config(state=tk.DISABLED, bg="#f1f2f6")

        def on_key_press(event, res_var, ent_widget):
            # Modifier 키들(Ctrl, Alt, Shift, Win 등)은 무시
            if event.keysym in ("Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R", "Win_L", "Win_R", "Tab"):
                return "break"
            
            key_name = event.keysym.upper()
            # 특수키 이름 매핑
            if key_name == "ESCAPE": key_name = "None"
            
            res_var.set(key_name)
            ent_widget.delete(0, tk.END)
            ent_widget.insert(0, key_name)
            return "break"

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
            
            # 체크박스 배치
            tk.Checkbutton(frame, text="Ctrl", variable=res["ctrl"]).pack(side=tk.LEFT)
            tk.Checkbutton(frame, text="Alt", variable=res["alt"]).pack(side=tk.LEFT)
            shift_cb = tk.Checkbutton(frame, text="Shift", variable=res["shift"])
            shift_cb.pack(side=tk.LEFT)
            
            # 초기화 버튼 (우측 끝)
            reset_btn = tk.Button(frame, text="초기화", command=lambda r=res: reset_single_shortcut(r), 
                                  bg="#e84118", fg="white", font=("Malgun Gothic", 8, "bold"), bd=0, padx=5, cursor="hand2")
            reset_btn.pack(side=tk.RIGHT, padx=(5, 0))

            # 키 입력 엔트리 (초기화 버튼 왼쪽)
            ent = tk.Entry(frame, width=10, justify='center', font=("Malgun Gothic", 9, "bold"))
            ent.insert(0, res["key"].get())
            ent.pack(side=tk.RIGHT, padx=5)
            ent.bind("<KeyPress>", lambda e, r=res["key"], w=ent: on_key_press(e, r, w))

            # Ctrl/Alt 변경 시 상태 업데이트 감시
            res["ctrl"].trace_add("write", lambda *a, r=res, s=shift_cb, e=ent: update_modifier_dependency(r, s, e))
            res["alt"].trace_add("write", lambda *a, r=res, s=shift_cb, e=ent: update_modifier_dependency(r, s, e))
            update_modifier_dependency(res, shift_cb, ent) # 초기 상태 설정

        def save_shortcuts_action():
            # 시스템 예약 단축키 블랙리스트
            BLACKLIST = [
                "alt+f4", "alt+tab", "ctrl+alt+delete", "ctrl+shift+escape", 
                "win+l", "ctrl+alt+tab", "alt+escape"
            ]

            new_shortcuts = {}
            for mode, config in results.items():
                k = config["key"].get()
                if k == "None":
                    new_shortcuts[mode] = ""
                    continue
                
                # 최소 하나 이상의 조합키(Ctrl/Alt)가 있어야 함
                if not config["ctrl"].get() and not config["alt"].get():
                    from tkinter import messagebox
                    messagebox.showwarning("단축키 설정 오류", f"'{dict(modes)[mode]}' 항목에 Ctrl 또는 Alt 조합키를 포함해야 합니다.\n(단독 키 지정은 시스템 키 입력을 방해할 수 있습니다.)")
                    return
                
                parts = []
                if config["ctrl"].get(): parts.append("ctrl")
                if config["alt"].get(): parts.append("alt")
                if config["shift"].get(): parts.append("shift")
                parts.append(k.lower())
                full_hk = "+".join(parts)

                # 블랙리스트 체크
                if full_hk in BLACKLIST:
                    from tkinter import messagebox
                    messagebox.showerror("금지된 단축키", f"'{full_hk.upper()}'는 시스템 예약 단축키이므로 사용할 수 없습니다.")
                    return

                new_shortcuts[mode] = full_hk
            
            self.shortcuts.update(new_shortcuts)
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
        """현재 활성화된 윈도우 탐색기 또는 바탕화면의 경로를 반환"""
        pythoncom.CoInitialize()
        try:
            # 포커스된 윈도우의 최상위 부모(Root)를 찾음 (자식 요소 포커스 대응)
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd: return None
            hwnd = win32gui.GetAncestor(hwnd, 2) # GA_ROOT
            
            window_title = win32gui.GetWindowText(hwnd)
            shell = win32com.client.Dispatch("Shell.Application")
            
            explorer_windows = []
            for window in shell.Windows():
                try:
                    # HWND 비교를 통해 해당 창의 모든 탭/윈도우 수집
                    if window.HWND == hwnd:
                        explorer_windows.append(window)
                except:
                    continue
            
            # 탐색기 창이 발견되지 않은 경우 바탕화면 여부 체크
            if not explorer_windows:
                class_name = win32gui.GetClassName(hwnd)
                if class_name in ["Progman", "WorkerW"]:
                    return os.path.join(os.environ["USERPROFILE"], "Desktop")
                return None
            
            # 윈도우 11 탭 환경 대응: 창 제목과 일치하는 탭 탐색
            if len(explorer_windows) > 1:
                for window in explorer_windows:
                    try:
                        # LocationName이나 Title이 창 제목에 포함되어 있는지 확인
                        loc_name = getattr(window, "LocationName", "")
                        display_name = window.Document.Folder.Title
                        if (loc_name and loc_name in window_title) or (display_name and display_name in window_title):
                            return window.Document.Folder.Self.Path
                    except:
                        continue
            
            # 일치하는 탭을 못 찾았거나 단일 창인 경우 첫 번째 경로 반환
            return explorer_windows[0].Document.Folder.Self.Path
        except:
            return None
        finally:
            pythoncom.CoUninitialize()

    def generate_filename(self):
        time_str = time.strftime('%Y%m%d_%H%M%S')
        return f"{time_str}_capture.{self.save_format}"

    def handle_explorer_paste(self):
        """Ctrl+Shift+V 발생 시 탐색기 창이면 클립보드 이미지를 저장합니다."""
        try:
            target_path = self.get_active_explorer_path()
            if not target_path: return

            # 클립보드 형식 확인
            is_image = False
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                    is_image = True
            finally:
                win32clipboard.CloseClipboard()

            if not is_image: return
            
            img = ImageGrab.grabclipboard()
            if img and isinstance(img, Image.Image):
                filename = self.generate_filename()
                filepath = os.path.join(target_path, filename)
                
                if self.save_format == "jpg":
                    img.convert("RGB").save(filepath, quality=95)
                else:
                    img.save(filepath)
                
                # 저장 완료 후 최근 목록 갱신
                self.root.after(100, self.refresh_recent_list)
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
        """이미지를 윈도우 클립보드에 표준 DIB 형식으로 복사"""
        output = io.BytesIO()
        img.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:] # BITMAPFILEHEADER(14바이트) 제외
        output.close()

        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
        except Exception as e:
            with open("debug_error.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.ctime()}] Copy to clipboard failed: {e}\n")

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
        menu.add_command(label="파일 위치 열기", command=lambda: self._open_file_location(filepath))
        menu.add_command(label="다른 이름으로 저장", command=lambda: self._save_thumbnail_as(filepath))
        menu.add_command(label="삭제", command=lambda: self._delete_thumbnail(filepath))
        menu.tk_popup(event.x_root, event.y_root)

    def _open_file_location(self, filepath):
        """윈도우 탐색기를 열어 해당 파일의 위치를 표시하고 파일을 선택함"""
        if not os.path.exists(filepath): return
        try:
            # explorer /select, "경로" 형식을 사용하여 파일 선택 상태로 탐색기 열기
            path = os.path.normpath(filepath)
            subprocess.run(['explorer', '/select,', path])
        except Exception as e:
            messagebox.showerror("오류", f"폴더를 열 수 없습니다: {e}")

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
        """목록을 초기화하고 첫 세트를 로드함"""
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        self.thumbnail_images.clear()
        self.loaded_count = 0
        
        # 그리드 열 가중치 설정 (중앙 정렬 효과를 위해)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        self.scrollable_frame.grid_columnconfigure(99, weight=1) 
        
        self.load_more_thumbnails()

    def on_canvas_scroll(self, *args):
        """스크롤 이벤트 발생 시 스크롤바 업데이트 및 추가 로드 체크"""
        self.scrollbar.set(*args)
        self.check_scroll_and_load()

    def check_scroll_and_load(self):
        """스크롤이 끝부분에 도달했는지 확인하여 추가 로드"""
        if self.loaded_count >= len(self.recent_captures):
            return
            
        low, high = self.canvas_recent.yview()
        if high > 0.85:
            self.load_more_thumbnails()

    def load_more_thumbnails(self):
        """다음 세트의 썸네일을 그리드 형태로 증분 로드"""
        start = self.loaded_count
        end = min(start + self.items_per_page, len(self.recent_captures))
        
        if start >= end:
            return

        # 가로 칸 수 계산 (썸네일 너비 약 180px 기준)
        canvas_w = self.canvas_recent.winfo_width()
        if canvas_w < 100: canvas_w = 200 # 초기 로딩 시 기본값
        cols = max(1, (canvas_w - 20) // 180)

        for i in range(start, end):
            filepath = self.recent_captures[i]
            if not os.path.exists(filepath): continue
            try:
                img = Image.open(filepath)
                img.thumbnail((160, 120))
                photo = ImageTk.PhotoImage(img)
                self.thumbnail_images.append(photo)
                
                thumb_frame = tk.Frame(self.scrollable_frame, bg="#1e272e", bd=0)
                # 그리드 배치: 중앙 정렬을 위해 컬럼 인덱스에 +1
                row = i // cols
                col = (i % cols) + 1
                thumb_frame.grid(row=row, column=col, padx=5, pady=5, sticky="n")
                
                lbl = tk.Label(thumb_frame, image=photo, bg="#2f3542", cursor="hand2")
                lbl.pack(pady=(5, 0))
                lbl.bind("<Double-Button-1>", lambda e, path=filepath: self.on_thumbnail_dblclick(path))
                lbl.bind("<Button-3>", lambda e, path=filepath: self._show_thumbnail_menu(e, path))
                
                # 파일명 라벨 (너무 길면 줄임)
                fname = os.path.basename(filepath)
                short_name = fname if len(fname) < 20 else fname[:17]+"..."
                name_lbl = tk.Label(thumb_frame, text=short_name, bg="#1e272e", fg="#a4b0be", font=("Malgun Gothic", 8))
                name_lbl.pack(pady=2)
                name_lbl.bind("<Button-3>", lambda e, path=filepath: self._show_thumbnail_menu(e, path))
            except Exception as e:
                print(f"Thumbnail error: {e}")
                
        self.loaded_count = end
        self.scrollable_frame.update_idletasks()
        self.canvas_recent.configure(scrollregion=self.canvas_recent.bbox("all"))

    def on_canvas_resize(self, event):
        """캔버스 크기 변경 시 썸네일 재배치 및 지연 로드 체크"""
        if self._resize_timer:
            self.root.after_cancel(self._resize_timer)
        self._resize_timer = self.root.after(100, self.regrid_thumbnails)
        
        # 캔버스 윈도우 너비 업데이트
        if hasattr(self, 'canvas_window'):
            self.canvas_recent.itemconfig(self.canvas_window, width=event.width)
        self.check_scroll_and_load()

    def regrid_thumbnails(self):
        """현재 너비에 맞춰 이미 로드된 위젯들의 그리드 위치를 재정렬"""
        if not self.scrollable_frame.winfo_exists(): return
        canvas_w = self.canvas_recent.winfo_width()
        if canvas_w < 100: return
        
        cols = max(1, (canvas_w - 20) // 180)
        widgets = self.scrollable_frame.winfo_children()
        
        for i, widget in enumerate(widgets):
            row = i // cols
            col = (i % cols) + 1
            widget.grid(row=row, column=col, padx=5, pady=5, sticky="n")
        
        self.canvas_recent.configure(scrollregion=self.canvas_recent.bbox("all"))

    def execute_capture(self, x1, y1, x2, y2):
        l, t, r, b = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        if r - l < 5 or b - t < 5: return
        
        try:
            img = ImageGrab.grab(bbox=(l, t, r, b), all_screens=True)
            self.copy_image_to_clipboard(img)
            
            # 클립보드 전용 모드이면 파일 저장 건너뜀
            if getattr(self, 'save_mode', 'both') == "clipboard":
                return

            filename = self.generate_filename(); filepath = os.path.join(self.save_dir, filename)
            if self.save_format == "jpg": img.convert("RGB").save(filepath, quality=95)
            else: img.save(filepath)
            self.recent_captures.insert(0, filepath)
            if len(self.recent_captures) > 100: self.recent_captures.pop()
            self.root.after(100, self.update_thumbnails)
        except Exception as e:
            print(f"Capture error: {e}")

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
