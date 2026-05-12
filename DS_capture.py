import tkinter as tk
from tkinter import filedialog, ttk, colorchooser, simpledialog, messagebox
import time
import os
import ctypes
from ctypes import wintypes
import io
import json
import math
import threading
import sys
import winreg
import hmac
import hashlib
import subprocess
from PIL import ImageGrab, Image, ImageDraw, ImageTk, ImageOps, ImageFont, ImageEnhance, ImageFilter
import keyboard
import pystray
from pystray import MenuItem as item

# --- [시작 프로그램 실행 경로 문제 해결] ---
# 실행 파일 경로로 작업 디렉토리 변경 (license.lic 파일을 찾지 못하는 문제 방지)
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

# DPI 인식 설정
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# [신규] 작업표시줄 아이콘 강제 설정 (AppUserModelID) - 오류 발생 시 무시하도록 보호
try:
    myappid = 'ds.capture.v1.0'
    # Windows 7 이상에서만 작동하는 API이므로 예외 처리 필수
    if hasattr(ctypes.windll.shell32, 'SetCurrentProcessExplicitAppUserModelID'):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

# --- [64비트 호환성 유지] Windows API 정의 ---
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
# -------------------------------------------

def get_base_dir():
    """실행 파일(EXE)이 위치한 실제 폴더 경로를 반환"""
    # 1. PyInstaller/Nuitka 등 패키징 환경 확인
    if getattr(sys, 'frozen', False):
        # 2. Nuitka 전용 환경 변수 확인
        for env_var in ['NUITKA_ONEFILE_DIRECTORY', 'NUITKA_PACKAGE_HOME']:
            val = os.environ.get(env_var)
            if val and os.path.exists(val):
                return os.path.abspath(val) if os.path.isdir(val) else os.path.dirname(os.path.abspath(val))
        
        # 3. PyInstaller 및 일반적인 EXE 실행 경로 (가장 확실함)
        # sys.executable은 언제나 실제 EXE의 위치를 가리킵니다.
        exe_path = os.path.abspath(sys.executable)
        return os.path.dirname(exe_path)
    
    # 4. 스크립트 실행 환경
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
CONFIG_FILE = os.path.join(BASE_DIR, "settings.json")
# 라이센스 폴더 경로 정의 (EXE와 같은 위치의 license 폴더 또는 EXE 바로 옆)
LICENSE_DIR = os.path.join(BASE_DIR, "license")
LICENSE_FILE = os.path.join(BASE_DIR, "license.lic")

# --- [빌드 정보] ---
BUILD_VERSION = "1.00.22"
BUILD_DATE = "2026-05-11"
BUILD_TIME = "15:57:48"

def get_resource_path(relative_path):
    """ 리소스 절대 경로 반환 (PyInstaller 지원) """
    if getattr(sys, 'frozen', False):
        # PyInstaller _MEIPASS 임시 폴더 확인
        base_path = getattr(sys, '_MEIPASS', BASE_DIR)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def set_window_icon(window):
    """모든 Toplevel/Tk 창에 아이콘 일괄 적용"""
    try:
        ico_path = get_resource_path("DS_capture.ico")
        if os.path.exists(ico_path):
            window.iconbitmap(ico_path)
    except:
        pass

def get_hwid():
    """기기 고유 정보를 조합하여 해싱된 HWID 생성"""
    try:
        # PowerShell 결과에서 첫 번째 줄(첫 번째 기기)만 가져오도록 수정 (C# Checker와 일치)
        cmd_mb = 'powershell "Get-CimInstance -ClassName Win32_BaseBoard | Select-Object -ExpandProperty SerialNumber"'
        mb_serial = subprocess.check_output(cmd_mb, shell=True).decode('cp949').strip().splitlines()[0].strip()
        
        cmd_disk = 'powershell "Get-CimInstance -ClassName Win32_DiskDrive | Select-Object -ExpandProperty SerialNumber"'
        disk_serial = subprocess.check_output(cmd_disk, shell=True).decode('cp949').strip().splitlines()[0].strip()
        
        raw_id = f"DS_{mb_serial}_{disk_serial}"
        hash_id = hashlib.sha256(raw_id.encode()).hexdigest().upper()
        return f"{hash_id[:4]}-{hash_id[4:8]}-{hash_id[8:12]}"
    except Exception as e:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            hash_id = hashlib.sha256(guid.encode()).hexdigest().upper()
            return f"G-{hash_id[:4]}-{hash_id[4:8]}"
        except:
            return f"ERR-{hash(str(e)) % 10000}"

# --- [보안 및 라이센스 설정] ---
SECRET_KEY = "DS_CAPTURE_SECRET_KEY_2026_@!" 

def check_license(app_name):
    """라이센스 유효성 검사 - 폴더 내 모든 .lic 파일을 스캔하여 HWID 매칭"""
    from datetime import datetime
    hwid = get_hwid()
    
    # 탐색할 폴더 리스트 (중앙 폴더 C:\license, EXE 옆 license 폴더, EXE 바로 옆)
    target_folders = [r"C:\license", LICENSE_DIR, BASE_DIR]
    
    # 매칭되는 HWID는 찾았으나 검증에 실패한 경우의 에러 메시지들
    fail_reason = ""

    for folder in target_folders:
        if not folder or not os.path.exists(folder): continue
        
        try:
            files = os.listdir(folder)
        except: continue

        for filename in files:
            if not filename.lower().endswith(".lic"): continue
            
            path = os.path.join(folder, filename)
            data_raw = None
            
            # 여러 인코딩 시도 (한글 포함 대응)
            for enc in ['utf-8-sig', 'utf-8', 'cp949']:
                try:
                    with open(path, 'r', encoding=enc) as f:
                        data_raw = json.load(f)
                    break
                except:
                    continue
            
            if data_raw is None:
                # 파일은 있으나 읽지 못한 경우 (JSON 형식 오류 등)
                fail_reason = f"파일을 읽을 수 없거나 형식이 잘못되었습니다: {filename}"
                continue

            try:
                # [수정] 복수 라이센스 지원 (리스트 형태 처리)
                license_list = data_raw if isinstance(data_raw, list) else [data_raw]
                
                found_ids = []
                for data in license_list:
                    f_hwid = data.get('hwid')
                    if f_hwid: found_ids.append(f_hwid)
                    
                    # 1. 기기 ID(HWID) 매칭 확인
                    if f_hwid != hwid: continue
                    
                    # 2. 프로그램 이름 일치 여부
                    if data.get('app_name') != app_name:
                        fail_reason = f"대상 기기({hwid})는 맞지만,\n이 라이센스는 {data.get('app_name')}용입니다."
                        continue
                    
                    # 3. 서명 검증
                    user_name = data.get('user_name')
                    expiry_str = data.get('expiry_date')
                    if not user_name or not expiry_str: continue
                    
                    msg = f"{str(data['hwid'])}{str(data['app_name'])}{str(expiry_str)}{str(user_name)}"
                    expected_signature = hmac.new(SECRET_KEY.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()
                    
                    if data.get('signature') != expected_signature:
                        fail_reason = f"사용자 '{user_name}'의 라이센스 서명이 일치하지 않습니다.\n(KeyGen에서 다시 발급받아 주세요)"
                        continue
                    
                    return True, data
                
                # 파일은 찾았으나 이 기기용 ID가 없을 때
                if not fail_reason:
                    ids_str = ", ".join(found_ids) if found_ids else "없음"
                    fail_reason = f"라이센스 파일({filename})을 확인했으나,\n이 기기({hwid})용 인증 정보가 없습니다.\n(파일 내 ID: {ids_str})"

            except Exception as e:
                fail_reason = f"라이센스 처리 중 오류: {str(e)}"
                continue

    # 최종적으로 찾지 못한 경우
    if fail_reason:
        msg = f"라이센스 검증 실패:\n{fail_reason}\n\n대상 앱: {app_name}"
    else:
        msg = f"유효한 라이센스 파일을 찾을 수 없습니다.\n대상 앱: {app_name}\n\n[방법] 실행 파일(.exe)과 같은 폴더에\n본인 기기 ID가 포함된 .lic 파일을 넣어주세요."
    
    show_license_error(hwid, msg)
    return False, None


def show_license_error(hwid, message):
    """라이센스 오류 팝업창"""
    root = tk.Tk()
    root.withdraw()
    
    err_win = tk.Toplevel(root)
    err_win.title("라이센스 인증 필요")
    set_window_icon(err_win)
    
    win_w, win_h = 450, 270
    sw, sh = err_win.winfo_screenwidth(), err_win.winfo_screenheight()
    err_win.geometry(f"{win_w}x{win_h}+{(sw-win_w)//2}+{(sh-win_h)//2}")
    err_win.config(bg="#1e272e")
    err_win.attributes("-topmost", True)
    
    tk.Label(err_win, text="라이센스 인증이 필요합니다.", bg="#1e272e", fg="#ff4757", 
             font=("Malgun Gothic", 12, "bold")).pack(pady=(25, 10))
    tk.Label(err_win, text=message, bg="#1e272e", fg="white", font=("Malgun Gothic", 9)).pack()
    
    tk.Label(err_win, text=f"기기 고유 ID: {hwid}", bg="#1e272e", fg="#00d2d3", 
             font=("Consolas", 11, "bold")).pack(pady=15)
             
    def copy_id():
        err_win.clipboard_clear()
        err_win.clipboard_append(hwid)
        from tkinter import messagebox
        messagebox.showinfo("복사 완료", "기기 ID가 복사되었습니다.\n관리자에게 전달하여 라이센스를 발급받으세요.")
        
    tk.Button(err_win, text="기기 ID 복사하기", command=copy_id, bg="#4b6584", fg="white", 
              font=("Malgun Gothic", 9, "bold"), padx=20, pady=5, bd=0, cursor="hand2").pack(pady=5)
              
    tk.Label(err_win, text="관리자에게 문의하세요.", bg="#1e272e", fg="#a4b0be", 
             font=("Malgun Gothic", 9)).pack(side=tk.BOTTOM, pady=10)
             
    err_win.bind("<Escape>", lambda e: sys.exit(0))
    err_win.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))
    root.mainloop()
# -------------------------------------------


class ResizableBox(tk.Toplevel):
    def __init__(self, parent, width, height, on_capture):
        super().__init__(parent)
        self.on_capture = on_capture
        set_window_icon(self) # 아이콘 설정 추가
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
        
        self.is_capturing = False # 연속 캡처 방지 및 상태 관리

    def close_box(self):
        if hasattr(self, 'catcher') and self.catcher.winfo_exists():
            self.catcher.destroy()
        self.master.deiconify()
        # self.master.attributes("-topmost", True)  <-- 이 부분을 제거하여 메인 창이 다시 topmost가 되지 않게 함
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
        if self.is_capturing: return
        self.is_capturing = True
        
        w, h = self.winfo_width(), self.winfo_height() - self.top_bar_h
        x = self.winfo_x()
        y = self.winfo_y() + self.top_bar_h if self.bar_position == "top" else self.winfo_y()
        
        # 캡처를 위해 잠시 숨김
        if hasattr(self, 'catcher') and self.catcher.winfo_exists():
            self.catcher.withdraw()
            
        self.withdraw()
        self.update()
        time.sleep(0.2)
        
        try:
            self.on_capture(x, y, x + w, y + h)
        finally:
            # 캡처 후 다시 표시 및 포커스 복구
            self.deiconify()
            if hasattr(self, 'catcher') and self.catcher.winfo_exists():
                self.catcher.deiconify()
            
            # self.attributes("-topmost", True)  <-- 이 줄을 삭제/주석 처리하여 캡처 후에도 항상 위가 되지 않게 함
            self.focus_force()
            if hasattr(self, 'catcher') and self.catcher.winfo_exists():
                self.catcher.focus_force()
            
            # 짧은 딜레이 후 다음 캡처 허용
            self.after(500, self._reset_capture_flag)

    def _reset_capture_flag(self):
        self.is_capturing = False

class ImageEditor(tk.Toplevel):
    """캡처 이미지 편집기 — 더블클릭으로 열림"""
    MAX_UNDO = 10
    PALETTE = ["#FF0000", "#FF8C00", "#FFFF00", "#008000", 
               "#0000FF", "#800080", "#FFFFFF", "#000000"]

    def __init__(self, parent, filepath, app):
        super().__init__(parent)
        self.withdraw() # 깜빡임 방지
        self.filepath = filepath
        self.app = app          # MainApp 참조
        self.attributes("-topmost", False)
        self.title(f"편집기 — {os.path.basename(filepath)}")
        set_window_icon(self)

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
        self.custom_fill_color = "#FF0000"  # 초기값 설정
        self.line_width   = 5
        self.font_family  = "Malgun Gothic"
        self.font_size    = 20
        self.fill_shape_var = tk.BooleanVar(value=False)

        # ── 드로잉 임시 변수 ──────────────────────────────────
        self._sx = self._sy = 0
        self._temp_items = []
        self._pen_pts    = []
        self.scale       = 1.0
        self._tk_img     = None
        self._tool_btns  = {}
        
        # [신규] 도구 전환 시 상태 복구를 위한 변수
        self.prev_lw = self.line_width
        self.prev_color = self.draw_color

        self._build_ui()
        self.after(50, self._fit_and_refresh)
        self._bind_events()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        
        self.deiconify() # 준비 완료 후 표시
        self.focus_force()

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
        
        self._size_lbl = tk.Label(row1, text="", bg="#1e272e", fg="#00d8d6", font=("Malgun Gothic", 10, "bold"))
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
        # ── 3행: 선 색상, 채우기 색상, 두께, 글꼴 ──
        row3 = tk.Frame(top_area, bg="#1e272e", pady=10, padx=12)
        row3.pack(fill=tk.X)
        
        def create_palette(parent, callback):
            for c in self.PALETTE:
                tk.Button(parent, bg=c, width=2, height=1, bd=1, relief="solid", cursor="hand2", 
                          command=lambda col=c: callback(col)).pack(side=tk.LEFT, padx=2)
            tk.Button(parent, text="⊕", bg="#485460", fg="white", bd=0, cursor="hand2", font=("Malgun Gothic",10, "bold"), 
                      command=self._pick_color if callback == self._set_color else self._pick_fill_color, padx=8).pack(side=tk.LEFT, padx=5)

        # 1. 선 색상 영역
        tk.Label(row3, text="선 색상:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0,6))
        create_palette(row3, self._set_color)
        self._color_ind = tk.Label(row3, bg=self.draw_color, width=3, height=1, relief="solid", bd=1)
        self._color_ind.pack(side=tk.LEFT, padx=3)

        tk.Frame(row3, bg="#808e9b", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=4)
        
        # 2. 선 두께 영역
        tk.Label(row3, text="선 두께:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0,6))
        self._width_var = tk.IntVar(value=self.line_width)
        tk.Spinbox(row3, from_=1, to=100, textvariable=self._width_var, width=4, font=("Malgun Gothic", 10), 
                   command=lambda: setattr(self,"line_width",self._width_var.get())).pack(side=tk.LEFT)
                   
        tk.Frame(row3, bg="#808e9b", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=4)

        # 3. 채우기 영역 (체크박스 포함)
        tk.Checkbutton(row3, text="채우기", variable=self.fill_shape_var, bg="#1e272e", fg="#d2dae2", 
                       selectcolor="#2f3640", activebackground="#1e272e", activeforeground="white",
                       font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(5,6))
        create_palette(row3, self._set_fill_color)
        self._fill_color_ind = tk.Label(row3, bg=self.custom_fill_color, width=3, height=1, relief="solid", bd=1)
        self._fill_color_ind.pack(side=tk.LEFT, padx=3)

        tk.Frame(row3, bg="#808e9b", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=4)
        
        # 4. 글꼴 영역
        tk.Label(row3, text="글꼴:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0,6))
        self._font_var = tk.StringVar(value=self.font_family)
        ttk.Combobox(row3, textvariable=self._font_var, values=["Malgun Gothic", "Consolas", "Impact"], state="readonly", width=10, font=("Malgun Gothic", 9)).pack(side=tk.LEFT, padx=2)
        self._font_var.trace_add("write", lambda *a: setattr(self,"font_family",self._font_var.get()))

        tk.Label(row3, text="크기:", bg="#1e272e", fg="#d2dae2", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(8,4))
        self._fsize_var = tk.IntVar(value=self.font_size)
        tk.Spinbox(row3, from_=8, to=120, textvariable=self._fsize_var, width=3, font=("Malgun Gothic", 10), 
                   command=lambda: setattr(self,"font_size",self._fsize_var.get())).pack(side=tk.LEFT)

        # ── 캔버스 영역 ─────────────────────────────
        self.canvas = tk.Canvas(self, bg="#2f3640", cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

    # ══════════════════════════════════════════════
    #  도구 선택 / 색상
    # ══════════════════════════════════════════════
    def _select_tool(self, name):
        prev_t = self.current_tool
        self.current_tool = name
        for n, b in self._tool_btns.items():
            b.config(bg="#0fbcf9" if n == name else "#718093")
        
        # 1. 형광펜으로 들어갈 때: 현재 설정을 저장하고 형광펜 전용 설정 적용
        if name == "highlight":
            if prev_t != "highlight":
                self.prev_lw = self.line_width
                self.prev_color = self.draw_color
            
            self.draw_color = "#FFFF00"
            self.line_width = 25
            self._color_ind.config(bg=self.draw_color)
            self._width_var.set(25)
            
        # 2. 형광펜에서 나갈 때: 저장했던 이전 설정을 복구
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
        if c:
            self._set_color(c)

    def _pick_fill_color(self):
        c = colorchooser.askcolor(color=self.custom_fill_color or self.draw_color, parent=self)[1]
        if c:
            self._set_fill_color(c)

    def _set_fill_color(self, color):
        self.custom_fill_color = color
        self._fill_color_ind.config(bg=color)
        self.fill_shape_var.set(True)

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
        try:
            r_filter = Image.Resampling.BILINEAR
        except AttributeError:
            r_filter = Image.BILINEAR
        disp = self.edit_img.convert("RGB").resize((dw, dh), r_filter)
        self._tk_img = ImageTk.PhotoImage(disp)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

    def _c2i(self, cx, cy):
        """캔버스 → 이미지 좌표"""
        return int(cx / self.scale), int(cy / self.scale)

    def _get_norm_rect(self, x1, y1, x2, y2):
        """정규화된 (x0, y0, x1, y1) 반환"""
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    def _is_shift_pressed(self, event):
        """Shift 키 눌림 여부 판정 (Tkinter + Windows API)"""
        return (event.state & 0x0001) or (ctypes.windll.user32.GetKeyState(0x10) & 0x8000)

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
        self.bind("<Escape>",                  lambda e: self._esc_close())
        self.bind("<Configure>",               self._on_configure)

    def _esc_close(self):
        self.destroy()
        return "break"

    def _on_configure(self, event):
        if event.widget == self:
            if hasattr(self, '_cfg_job') and self._cfg_job is not None:
                self.after_cancel(self._cfg_job)
            self._cfg_job = self.after(50, self._fit_and_refresh)

    def _on_press(self, event):
        self._sx, self._sy = event.x, event.y
        self._pen_pts = [(event.x, event.y)]
        for item in self._temp_items:
            self.canvas.delete(item)
        self._temp_items = []

    def _on_drag(self, event):
        # 사각형, 원, 직선 등 고무줄 형태의 도구만 기존 가이드를 지움
        if self.current_tool not in ["pen", "highlight"]:
            for item in self._temp_items:
                self.canvas.delete(item)
            self._temp_items = []
            
        x, y = event.x, event.y
        sx, sy = self._sx, self._sy
        col = self.draw_color
        # [수정] 미리보기 굵기에 배율을 곱해 실제 저장될 굵기와 일치시킴
        lw  = max(1, int(self._width_var.get() * self.scale))
        t   = self.current_tool

        if t in ["pen", "highlight"]:
            is_shift = self._is_shift_pressed(event)
            if t == "highlight":
                # 형광펜은 항상 수평 고정
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
                    self._temp_items.append(
                        self.canvas.create_line(*pts[-2], *pts[-1], fill=col, width=lw,
                                               capstyle=tk.ROUND, joinstyle=tk.ROUND))
        elif t == "line":
            self._temp_items.append(self.canvas.create_line(sx,sy,x,y,fill=col,width=lw))
        elif t == "arrow":
            self._temp_items.append(self.canvas.create_line(sx,sy,x,y,fill=col,width=lw,
                                    arrow=tk.LAST, arrowshape=(16,20,6)))
        elif t == "rect":
            x0, y0, x1, y1 = self._get_norm_rect(sx, sy, x, y)
            if self.fill_shape_var.get():
                fill_c = self.custom_fill_color or col
                self._temp_items.append(self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill_c, outline=col, width=lw))
            else:
                self._temp_items.append(self.canvas.create_rectangle(x0, y0, x1, y1, outline=col, width=lw))
        elif t == "ellipse":
            x0, y0, x1, y1 = self._get_norm_rect(sx, sy, x, y)
            if self.fill_shape_var.get():
                fill_c = self.custom_fill_color or col
                self._temp_items.append(self.canvas.create_oval(x0, y0, x1, y1, fill=fill_c, outline=col, width=lw))
            else:
                self._temp_items.append(self.canvas.create_oval(x0, y0, x1, y1, outline=col, width=lw))
        elif t in ("mosaic","crop","text"):
            x0, y0, x1, y1 = self._get_norm_rect(sx, sy, x, y)
            self._temp_items.append(self.canvas.create_rectangle(x0, y0, x1, y1,
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
            if self._is_shift_pressed(event):
                if abs(x - sx) > abs(y - sy): y = sy
                else: x = sx
                self._pen_pts = [(sx, sy), (x, y)]
            
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
            y = sy # 수평 고정
            pts = [self._c2i(px, py) for px, py in [(sx, sy), (x, y)]]
            
            overlay = Image.new("RGBA", self.edit_img.size, (0,0,0,0))
            ov_draw = ImageDraw.Draw(overlay)
            # 형광펜은 선명도 유지를 위해 블러 반경을 최소화(0.4), 투명도는 20% 수준(50)
            ov_draw.line(pts, fill=(r,g,b,50), width=lw, joint="round")
            overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.4))
            self.edit_img = Image.alpha_composite(self.edit_img, overlay)

        elif t == "mosaic":
            x0, y0, x1, y1 = self._get_norm_rect(isx, isy, ix, iy)
            iw, ih = self.edit_img.size
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(iw, x1), min(ih, y1)
            if x1 - x0 > 4 and y1 - y0 > 4:
                region = self.edit_img.crop((x0, y0, x1, y1))
                small = region.resize((max(1, (x1 - x0) // 10), max(1, (y1 - y0) // 10)), Image.BOX)
                blurred = small.resize((x1 - x0, y1 - y0), Image.NEAREST)
                self.edit_img.paste(blurred, (x0, y0))

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
    def __init__(self, license_data=None):
        self.license_data = license_data or {}
        # [수정] AppUserModelID 중복 설정 제거 — 모듈 최상단에서 1회만 호출

        self.root = tk.Tk()
        set_window_icon(self.root)
        
        # 타이틀에 라이센스 사용자 및 단축 버전 표시 (x.xx 형식)
        user_info = self.license_data.get('user_name', 'Free User')
        short_ver = ".".join(BUILD_VERSION.split(".")[:2])
        self.root.title(f"DS Capture {short_ver} - [{user_info}]")
        
        # --- [시작프로그램 모드 처리] ---
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
        
        # [수정] 기본값 설정 및 설정 불러오기
        self.save_dir = BASE_DIR
        self.save_format = "png"
        self.shortcuts = {"fixed": None, "drag": None, "full": None}
        self.recent_captures = []
        self.thumbnail_images = []
        self.close_action = "tray"
        
        self.load_config() # 시작할 때 저장된 설정 읽기
        
        # [신규] Esc 누르면 창 닫기 (메인 윈도우)
        self.root.bind("<Escape>", self._on_esc_main)

        # 설정 파일이 없으면 기본값으로 즉시 생성
        if not os.path.exists(CONFIG_FILE):
            self.save_config()

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

        # 불러온 단축키 즉시 적용
        self.apply_shortcuts()
        
        # 최근 캡처 목록 화면에 렌더링
        self.update_thumbnails()

        self.create_tray_icon()
        
        # 모든 초기화가 끝난 후, 시작프로그램 모드라면 창을 숨김
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
        
        # [수정] Esc 누르면 설정 창만 닫히도록 (확실한 이벤트 차단)
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

        # [신규] 하단에 전체 버전 정보 표시
        tk.Label(pop, text=f"Version {BUILD_VERSION} (Build: {BUILD_DATE})", 
                 bg="#1e272e", fg="#57606f", font=("Malgun Gothic", 8)).pack(side=tk.BOTTOM, pady=10)

        self.update_format_buttons()
        self.update_close_action_buttons()
        self.update_startup_buttons()
        
        # --- [빌드 정보 표시] ---
        tk.Frame(btn_con, height=1, bg="#3d3d3d").pack(fill=tk.X, pady=(25, 10)) # 구분선
        
        info_f = tk.Frame(btn_con, bg="#1e272e")
        info_f.pack(fill=tk.X)
        
        tk.Label(info_f, text=f"Version: {BUILD_VERSION}", bg="#1e272e", fg="#a4b0be", 
                 font=("Malgun Gothic", 8)).pack(side=tk.LEFT)
        tk.Label(info_f, text=f"Build: {BUILD_DATE} {BUILD_TIME}", bg="#1e272e", fg="#a4b0be", 
                 font=("Malgun Gothic", 8)).pack(side=tk.RIGHT)
        
        pop.focus_force()

    # --- [신규] 설정 저장/불러오기 로직 ---
    def save_config(self):
        """현재 설정을 JSON 파일로 저장합니다."""
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
            from tkinter import messagebox
            messagebox.showerror("저장 오류", f"설정 파일을 저장하는 중 오류가 발생했습니다:\n{str(e)}\n\n경로: {CONFIG_FILE}")

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
            # 인자 포함 여부와 상관없이 경로가 일치하는지 확인
            return f'"{path}"' in value
        except Exception:
            return False

    def set_startup(self, enable):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if enable:
                path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
                # 시작프로그램 등록 시 --startup 인자 추가
                winreg.SetValueEx(key, "DSCapture", 0, winreg.REG_SZ, f'"{path}" --startup')
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

    def _on_esc_main(self, event):
        # [수정] 메인 윈도우 외에 다른 Toplevel 창(설정, 편집기 등)이 열려 있다면 
        # 메인 윈도우가 닫히지 않도록 보호 (이벤트 전파 문제 해결)
        for child in self.root.winfo_children():
            if isinstance(child, tk.Toplevel) and child.winfo_exists() and child.winfo_viewable():
                return "break"

        # 메인 윈도우가 직접 포커스를 가졌을 때만 동작하도록 보호
        if event.widget == self.root:
            self.on_close_window()
        return "break"

    def set_save_location(self):
        d = filedialog.askdirectory(initialdir=self.save_dir)
        if d: 
            self.save_dir = d
            self.save_config() # 경로 변경 시 저장

    def popup_shortcut_settings(self):
        pop = tk.Toplevel(self.root)
        pop.title("단축키 설정")
        set_window_icon(pop)
        pop.geometry("420x350")
        pop.attributes("-topmost", False)
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
        
        # [추가] 단축키 설정 창에서도 Esc로 닫기 지원
        pop.bind("<Escape>", lambda e: pop.destroy())
        pop.focus_force()

    # --- 트레이 아이콘 및 기타 로직 (기존과 동일) ---
    def create_tray_icon(self):
        try:
            icon_path = get_resource_path("DS_capture.ico")
            if os.path.exists(icon_path):
                raw_img = Image.open(icon_path).convert("RGBA")
                # 아이콘의 투명 여백을 제거하여 알맹이만 추출 (더 크게 보이게 함)
                bbox = raw_img.getbbox()
                if bbox:
                    icon_img = raw_img.crop(bbox).resize((64, 64), Image.LANCZOS)
                else:
                    icon_img = raw_img.resize((64, 64), Image.LANCZOS)
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
        # self.root.attributes("-topmost", True)  <-- 이 부분을 제거하여 창을 다시 띄울 때 항상 위가 되지 않게 함

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
        ov.withdraw() # 처음엔 숨김 상태로 생성 (깜빡임 방지)
        set_window_icon(ov)
        ov.attributes("-fullscreen", True, "-topmost", True)
        ov.config(bg="black") # 배경을 검은색으로 미리 지정
        
        cv = tk.Canvas(ov, highlightthickness=0, cursor="none", bg="black")
        cv.pack(fill=tk.BOTH, expand=True)
        
        ov.dark_photo = ImageTk.PhotoImage(dark_img)
        cv.create_image(0, 0, image=ov.dark_photo, anchor="nw")
        
        def _on_esc_ov(e):
            ov.destroy()
            self.show_window()
            return "break"
        ov.bind("<Escape>", _on_esc_ov)
        ov.deiconify() # 준비 완료 후 표시
        ov.focus_force()
        rd = {"id": None, "tid": None, "tbg": None, "x": 0, "y": 0, "vline": None, "hline": None, "clear_img": None, "last_render": 0}
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
            
            x1, y1 = x0 - dx if is_ctrl else x0, y0 - dy if is_ctrl else y0
            x2, y2 = x0 + dx, y0 + dy
                
            return x1, y1, x2, y2

        def on_m(e):
            x1, y1, x2, y2 = get_rect(e)
            
            # [최적화] 선과 테두리는 즉시 업데이트 (부드러운 마우스 움직임)
            cv.coords(rd["id"], x1, y1, x2, y2)
            cv.coords(rd["vline"], e.x, 0, e.x, self.sh)
            cv.coords(rd["hline"], 0, e.y, self.sw, e.y)
            
            w, h = int(abs(x2 - x1)), int(abs(y2 - y1))
            tx, ty = min(x1, x2), min(y1, y2) - 5
            
            # [최적화] 이미지 크롭 및 텍스트 업데이트는 쓰로틀링 적용 (약 30fps)
            now = time.time()
            if now - rd["last_render"] > 0.03: 
                cv.itemconfig(rd["tid"], text=f" {w} x {h} ")
                b = cv.bbox(rd["tid"])
                cv.coords(rd["tbg"], b[0]-2, b[1]-2, b[2]+2, b[3]+2)
                cv.coords(rd["tid"], tx, ty)
                
                if w > 0 and h > 0:
                    cx_min, cy_min = min(x1, x2), min(y1, y2)
                    cropped = screen_img.crop((cx_min, cy_min, cx_min + w, cy_min + h))
                    ov.active_photo = ImageTk.PhotoImage(cropped)
                    cv.itemconfig(rd["clear_img"], image=ov.active_photo)
                    cv.coords(rd["clear_img"], cx_min, cy_min)
                rd["last_render"] = now

        def on_r(e):
            x1, y1, x2, y2 = get_rect(e)
            cx_min, cy_min = min(x1, x2), min(y1, y2)
            cx_max, cy_max = max(x1, x2), max(y1, y2)
            ov.destroy()
            self.execute_capture(cx_min, cy_min, cx_max, cy_max)
            self.show_window()
        cv.bind("<Motion>", on_hover)
        cv.bind("<Button-1>", on_p)
        cv.bind("<B1-Motion>", on_m)
        cv.bind("<ButtonRelease-1>", on_r)

    def full_capture(self):
        self.root.withdraw()
        self.root.update()
        time.sleep(0.3)
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
                
                name_lbl = tk.Label(thumb_frame, text=os.path.basename(filepath), bg="#2f3542", fg="white", font=("Malgun Gothic", 8))
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
            if self.save_format == "jpg":
                img.convert("RGB").save(filepath, quality=95)
            else:
                img.save(filepath)
            
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

def enforce_single_instance():
    mutex_name = "Global\\DSCapture_Unique_Instance_Mutex"
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
        return False, None
    return True, mutex

def focus_existing_window():
    """이미 실행 중인 DS Capture 창을 찾아 활성화함"""
    def callback(hwnd, extra):
        title = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, title, 256)
        if title.value.startswith("DS Capture"):
            # SW_RESTORE(9)로 최소화 해제 후 앞으로 가져오기
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return False # 찾았으므로 중단
        return True

    enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    # 콜백 함수가 가비지 컬렉션되지 않도록 변수에 할당 후 사용
    cb_ptr = enum_windows_proc(callback)
    ctypes.windll.user32.EnumWindows(cb_ptr, 0)

if __name__ == "__main__":
    is_unique, mutex = enforce_single_instance()
    if not is_unique:
        focus_existing_window()
        sys.exit(0)
        
    # 라이센스 체크 (프로그램명: DS_CAPTURE)
    is_valid, lic_data = check_license("DS_CAPTURE")
    if is_valid:
        app = MainApp(lic_data)
        app.root.mainloop()
