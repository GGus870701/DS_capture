import os
import sys
import ctypes

# 빌드 정보
BUILD_VERSION = "1.00.30"
BUILD_DATE = "2026-05-15"
BUILD_TIME = "12:01:36"

def get_base_dir():
    """실행 파일(EXE)이 위치한 실제 폴더 경로를 반환"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(sys.argv[0]))

BASE_DIR = get_base_dir()
CONFIG_FILE = os.path.join(BASE_DIR, "settings.json")
LICENSE_DIR = os.path.join(BASE_DIR, "license")

def get_resource_path(relative_path):
    """리소스 절대 경로 반환 (PyInstaller 지원)"""
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', BASE_DIR)
    else:
        # 이 파일이 core/utils.py에 있으므로 상위 폴더를 기준으로 함
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def set_window_icon(window):
    """모든 Toplevel/Tk 창에 아이콘 일괄 적용"""
    try:
        ico_path = get_resource_path("icon/DS_capture.ico")
        if os.path.exists(ico_path):
            window.iconbitmap(ico_path)
    except:
        pass

def set_qt_window_icon(window):
    """PySide6 윈도우에 아이콘 적용"""
    try:
        from PySide6.QtGui import QIcon
        ico_path = get_resource_path("icon/DS_capture.ico")
        if os.path.exists(ico_path):
            window.setWindowIcon(QIcon(ico_path))
    except:
        pass
