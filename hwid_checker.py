import tkinter as tk
from tkinter import messagebox
import subprocess
import hashlib

def get_hwid():
    """기기 고유 정보를 조합하여 해싱된 HWID 생성"""
    try:
        # PowerShell을 통해 메인보드 및 디스크 시리얼 추출 (wmic 미지원 환경 대응)
        cmd_mb = 'powershell "Get-CimInstance -ClassName Win32_BaseBoard | Select-Object -ExpandProperty SerialNumber"'
        mb_serial = subprocess.check_output(cmd_mb, shell=True).decode('cp949').strip()
        
        cmd_disk = 'powershell "Get-CimInstance -ClassName Win32_DiskDrive | Select-Object -ExpandProperty SerialNumber"'
        disk_serial = subprocess.check_output(cmd_disk, shell=True).decode('cp949').strip()
        
        # 정보 조합 및 해싱
        raw_id = f"DS_{mb_serial}_{disk_serial}"
        hash_id = hashlib.sha256(raw_id.encode()).hexdigest().upper()
        return f"{hash_id[:4]}-{hash_id[4:8]}-{hash_id[8:12]}"
    except Exception as e:
        # 최후의 보루: 레지스트리 MachineGuid 사용
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            hash_id = hashlib.sha256(guid.encode()).hexdigest().upper()
            return f"G-{hash_id[:4]}-{hash_id[4:8]}"
        except:
            return f"ERR-{hash(str(e)) % 10000}"

class HWIDChecker:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DS HWID Checker")
        
        # 화면 중앙 배치
        win_w, win_h = 400, 200
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{win_w}x{win_h}+{(sw-win_w)//2}+{(sh-win_h)//2}")
        self.root.resizable(False, False)
        self.root.config(bg="#1e272e")
        
        # 폰트 설정
        self.main_font = ("Malgun Gothic", 10, "bold")
        self.id_font = ("Consolas", 14, "bold")
        
        # UI 구성
        tk.Label(self.root, text="고객님의 기기 고유 ID (HWID)", bg="#1e272e", fg="#a4b0be", font=self.main_font).pack(pady=(20, 5))
        
        self.hwid = get_hwid()
        self.id_label = tk.Label(self.root, text=self.hwid, bg="#1e272e", fg="#00d2d3", font=self.id_font)
        self.id_label.pack(pady=5)
        
        btn_copy = tk.Button(self.root, text="ID 복사하기", command=self.copy_id, bg="#4b6584", fg="white", 
                             font=self.main_font, padx=20, pady=5, bd=0, cursor="hand2")
        btn_copy.pack(pady=10)
        
        tk.Label(self.root, text="관리자에게 문의하세요.", bg="#1e272e", fg="#778ca3", font=("Malgun Gothic", 9)).pack(side=tk.BOTTOM, pady=10)

    def copy_id(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.hwid)
        messagebox.showinfo("성공", "기기 ID가 클립보드에 복사되었습니다.")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    HWIDChecker().run()
