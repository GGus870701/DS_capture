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
import win32gui
import win32com.client
import pythoncom
import DS_image_editor

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
    """실행 파일(EXE)이 위치한 실제 폴더 경로를 반환 (상단에서 이미 chdir 완료)"""
    return os.getcwd()

BASE_DIR = get_base_dir()
CONFIG_FILE = os.path.join(BASE_DIR, "settings.json")
# 라이센스 폴더 경로 정의 (EXE와 같은 위치의 license 폴더 또는 EXE 바로 옆)
LICENSE_DIR = os.path.join(BASE_DIR, "license")

# --- [빌드 정보] ---
BUILD_VERSION = "1.00.24"
BUILD_DATE = "2026-05-12"
BUILD_TIME = "11:16:22"

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

# --- [메인 실행 제어] -----------------------
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
    cb_ptr = enum_windows_proc(callback)
    ctypes.windll.user32.EnumWindows(cb_ptr, 0)

def main_entry():
    """프로그램 진입점: 중복 실행 방지 및 라이센스 체크"""
    # [신규] 이미지 편집기 모드로 실행된 경우 (멀티 엔진 방식)
    if "--editor" in sys.argv and len(sys.argv) >= 3:
        img_path = sys.argv[2]
        DS_image_editor.run_editor(img_path)
        sys.exit(0)

    is_unique, mutex = enforce_single_instance()
    if not is_unique:
        focus_existing_window()
        sys.exit(0)
        
    # 라이센스 체크 (프로그램명: DS_CAPTURE)
    is_valid, lic_data = check_license("DS_CAPTURE")
    if is_valid:
        app = MainApp(lic_data)
        app.root.mainloop()
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
            
        # [신규] 탐색기 이미지 붙여넣기 (Ctrl+V) 등록
        try:
            keyboard.add_hotkey('ctrl+v', self.handle_explorer_paste, suppress=False)
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

    # --- [신규] 탐색기 이미지 붙여넣기 기능 ---
    def get_active_explorer_path(self):
        """현재 활성화된 윈도우 탐색기 또는 바탕화면의 경로를 반환합니다."""
        # COM 초기화 (멀티스레드 환경 대응)
        pythoncom.CoInitialize()
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd: return None
            
            # 탐색기 창 확인
            shell = win32com.client.Dispatch("Shell.Application")
            for window in shell.Windows():
                if window.HWND == hwnd:
                    # 일반 탐색기 폴더 경로
                    return window.Document.Folder.Self.Path
            
            # 바탕화면 확인 (Progman 또는 WorkerW 클래스)
            class_name = win32gui.GetClassName(hwnd)
            if class_name in ["Progman", "WorkerW"]:
                return os.path.join(os.environ["USERPROFILE"], "Desktop")
                
        except Exception:
            pass
        finally:
            pythoncom.CoUninitialize()
        return None

    def generate_filename(self):
        """현재 시간과 설정된 포맷을 바탕으로 파일명을 생성합니다."""
        time_str = time.strftime('%Y%m%d_%H%M%S')
        return f"{time_str}_capture.{self.save_format}"

    def handle_explorer_paste(self):
        """Ctrl+V 발생 시 탐색기 창이면 클립보드 이미지를 저장합니다."""
        target_path = self.get_active_explorer_path()
        if not target_path:
            return

        # 클립보드에서 이미지 가져오기
        try:
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                filename = self.generate_filename()
                filepath = os.path.join(target_path, filename)
                
                if self.save_format == "jpg":
                    img.convert("RGB").save(filepath, quality=95)
                else:
                    img.save(filepath)
                
        except Exception:
            pass

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
        rd = {"id": None, "tid": None, "tbg": None, "x": 0, "y": 0, "vline": None, "hline": None, "last_render": 0}
        
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
            
            # [최적화] 선과 테두리 좌표만 즉시 업데이트 (이미지 연산을 제거하여 100% 부드러움 확보)
            cv.coords(rd["id"], x1, y1, x2, y2)
            cv.coords(rd["vline"], e.x, 0, e.x, self.sh)
            cv.coords(rd["hline"], 0, e.y, self.sw, e.y)
            
            w, h = int(abs(x2 - x1)), int(abs(y2 - y1))
            tx, ty = min(x1, x2), min(y1, y2) - 5
            
            # 텍스트 정보 업데이트 (최소한의 오버헤드)
            cv.itemconfig(rd["tid"], text=f" {w} x {h} ")
            b = cv.bbox(rd["tid"])
            cv.coords(rd["tbg"], b[0]-2, b[1]-2, b[2]+2, b[3]+2)
            cv.coords(rd["tid"], tx, ty)

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
        """썸네일 더블클릭 시 이미지 편집기 프로세스로 오픈"""
        if os.path.exists(filepath):
            try:
                # [수정] 멀티 엔진(One File) 방식: 자기 자신(sys.executable)을 --editor 인자와 함께 실행
                if getattr(sys, 'frozen', False):
                    # EXE 실행 환경
                    subprocess.Popen([sys.executable, "--editor", filepath])
                else:
                    # 스크립트 실행 환경
                    subprocess.Popen([sys.executable, sys.argv[0], "--editor", filepath])
                
                # 편집기가 종료된 후 목록을 새로고침하고 싶다면 
                # .wait()를 쓸 수 없으므로(메인 UI가 멈춤) 별도 스레드에서 감시하거나 
                # 단순히 일정 시간 후 또는 창이 포커스를 얻을 때 갱신하도록 구성 가능
                self.root.after(2000, self.update_thumbnails) # 2초 후 가볍게 갱신 시도
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
        filename = self.generate_filename()
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

if __name__ == "__main__":
    main_entry()
