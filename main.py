import sys
import ctypes
import os
import tkinter as tk
from core.utils import set_window_icon
from license_core import check_license
from ui.main_app import MainApp

# Qt DPI 경고 숨기기 및 DPI 설정
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"

try:
    # Tkinter를 위해 DPI 인식 설정
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass

# 작업표시줄 아이콘 그룹화 설정
try:
    myappid = 'ds.capture.v1.0'
    if hasattr(ctypes.windll.shell32, 'SetCurrentProcessExplicitAppUserModelID'):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

def enforce_single_instance():
    """중복 실행 방지 Mutex 설정"""
    mutex_name = "Global\\DSCapture_Unique_Instance_Mutex"
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
        return False, None
    return True, mutex

def focus_existing_window():
    """이미 실행 중인 창을 찾아 활성화"""
    def callback(hwnd, extra):
        title = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, title, 256)
        if title.value.startswith("DS Capture"):
            ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return False
        return True

    enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    cb_ptr = enum_windows_proc(callback)
    ctypes.windll.user32.EnumWindows(cb_ptr, 0)

def main_entry():
    # 1. 이미지 편집기 모드로 실행된 경우 (멀티 프로세스)
    if "--editor" in sys.argv and len(sys.argv) >= 3:
        from modules import image_editor
        img_path = sys.argv[2]
        image_editor.run_editor(img_path)
        sys.exit(0)

    # 2. 중복 실행 체크
    is_unique, mutex = enforce_single_instance()
    if not is_unique:
        focus_existing_window()
        sys.exit(0)
        
    # 3. 라이센스 유효성 검사
    is_valid, lic_data = check_license("DS_CAPTURE", set_window_icon)
    if is_valid:
        # 4. 메인 앱 실행
        app = MainApp(lic_data)
        app.root.mainloop()

if __name__ == "__main__":
    # 실행 파일 경로로 작업 디렉토리 고정
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
    main_entry()
