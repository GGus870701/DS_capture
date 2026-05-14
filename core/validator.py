import os
import sys
import json
import hashlib
import hmac
import subprocess
import winreg
import tkinter as tk
from tkinter import messagebox
from core.utils import LICENSE_DIR, BASE_DIR

# [보안 및 라이센스 설정]
SECRET_KEY = "DASAN_TECHNOLOGY_SAFETY_SECRET_KEY_@!"

def get_hwid():
    """기기 고유 정보를 조합하여 해싱된 HWID 생성"""
    try:
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

def show_license_error(hwid, message, icon_setter=None):
    """라이센스 오류 팝업창"""
    root = tk.Tk()
    root.withdraw()
    
    err_win = tk.Toplevel(root)
    err_win.title("라이센스 인증 필요")
    if icon_setter:
        icon_setter(err_win)
    
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
        messagebox.showinfo("복사 완료", "기기 ID가 복사되었습니다.\n관리자에게 전달하여 라이센스를 발급받으세요.")
        
    tk.Button(err_win, text="기기 ID 복사하기", command=copy_id, bg="#4b6584", fg="white", 
              font=("Malgun Gothic", 9, "bold"), padx=20, pady=5, bd=0, cursor="hand2").pack(pady=5)
              
    tk.Label(err_win, text="관리자에게 문의하세요.", bg="#1e272e", fg="#a4b0be", 
             font=("Malgun Gothic", 9)).pack(side=tk.BOTTOM, pady=10)
             
    err_win.bind("<Escape>", lambda e: sys.exit(0))
    err_win.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))
    root.mainloop()

def check_license(app_name, icon_setter=None):
    """라이센스 유효성 검사"""
    hwid = get_hwid()
    
    # 탐색할 폴더 리스트
    target_folders = [r"C:\license", LICENSE_DIR, BASE_DIR]
    
    fail_reason = ""
    for folder in target_folders:
        if not folder or not os.path.exists(folder): continue
        try:
            files = os.listdir(folder)
            for filename in files:
                if not filename.lower().endswith(".lic"): continue
                path = os.path.join(folder, filename)
                data_raw = None
                for enc in ['utf-8-sig', 'utf-8', 'cp949']:
                    try:
                        with open(path, 'r', encoding=enc) as f:
                            data_raw = json.load(f)
                        break
                    except: continue
                
                if data_raw is None: continue

                license_list = data_raw if isinstance(data_raw, list) else [data_raw]
                for data in license_list:
                    if data.get('hwid') != hwid: continue
                    if data.get('app_name') not in [app_name, "ALL_ACCESS"]: continue
                    
                    user_name = data.get('user_name')
                    expiry_str = data.get('expiry_date')
                    msg = f"{str(data['hwid'])}{str(data['app_name'])}{str(expiry_str)}{str(user_name)}"
                    expected_signature = hmac.new(SECRET_KEY.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()
                    
                    if data.get('signature') == expected_signature:
                        return True, data
        except: continue

    msg = f"유효한 라이센스를 찾을 수 없습니다.\n대상 앱: {app_name}"
    show_license_error(hwid, msg, icon_setter)
    return False, None
