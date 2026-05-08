import tkinter as tk
from tkinter import messagebox, ttk
import hmac
import hashlib
import json
import os
from datetime import datetime, timedelta

# capture.py와 반드시 동일해야 함
SECRET_KEY = "DS_CAPTURE_SECRET_KEY_2026_@!" 

class LicenseKeyGen:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DS License KeyGen (Admin Only)")
        
        win_w, win_h = 500, 450
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{win_w}x{win_h}+{(sw-win_w)//2}+{(sh-win_h)//2}")
        self.root.config(bg="#2f3640")
        
        style = ttk.Style()
        style.theme_use('clam')
        
        self.main_font = ("Malgun Gothic", 10)
        self.header_font = ("Malgun Gothic", 12, "bold")
        
        # UI 구성
        tk.Label(self.root, text="DS 라이센스 발급기", bg="#2f3640", fg="#f5f6fa", font=self.header_font).pack(pady=20)
        
        container = tk.Frame(self.root, bg="#2f3640")
        container.pack(padx=30, fill=tk.X)
        
        # 1. 프로그램 선택
        tk.Label(container, text="대상 프로그램 (App Name):", bg="#2f3640", fg="#dcdde1", font=self.main_font).pack(anchor="w")
        self.app_name_var = tk.StringVar(value="DS_CAPTURE")
        app_list = ["DS_CAPTURE", "OTHER_TOOL_A", "OTHER_TOOL_B"]
        self.app_combo = ttk.Combobox(container, textvariable=self.app_name_var, values=app_list, state="readonly", font=self.main_font)
        self.app_combo.pack(fill=tk.X, pady=(5, 15))
        
        # 2. HWID 입력
        tk.Label(container, text="사용자 기기 ID (HWID):", bg="#2f3640", fg="#dcdde1", font=self.main_font).pack(anchor="w")
        self.hwid_entry = tk.Entry(container, font=("Consolas", 11), bg="#353b48", fg="white", insertbackground="white", bd=0)
        self.hwid_entry.pack(fill=tk.X, pady=(5, 15), ipady=5)
        
        # 3. 만료일 설정
        tk.Label(container, text="만료 기한 (YYYY-MM-DD):", bg="#2f3640", fg="#dcdde1", font=self.main_font).pack(anchor="w")
        date_frame = tk.Frame(container, bg="#2f3640")
        date_frame.pack(fill=tk.X, pady=(5, 15))
        
        self.expiry_entry = tk.Entry(date_frame, font=("Consolas", 11), bg="#353b48", fg="white", insertbackground="white", bd=0)
        self.expiry_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        self.expiry_entry.insert(0, (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"))
        
        tk.Button(date_frame, text="영구", command=lambda: self.set_expiry("PERMANENT"), bg="#7f8c8d", fg="white", bd=0, padx=10).pack(side=tk.LEFT, padx=(5, 0))
        
        # 4. 발급 버튼
        btn_gen = tk.Button(self.root, text="라이센스 파일 생성 (license.lic)", command=self.generate_license, 
                            bg="#44bd32", fg="white", font=self.header_font, pady=10, bd=0, cursor="hand2")
        btn_gen.pack(pady=20, fill=tk.X, padx=30)

    def set_expiry(self, val):
        self.expiry_entry.delete(0, tk.END)
        self.expiry_entry.insert(0, val)

    def generate_license(self):
        hwid = self.hwid_entry.get().strip()
        app_name = self.app_name_var.get()
        expiry = self.expiry_entry.get().strip()
        
        if not hwid:
            messagebox.showerror("오류", "HWID를 입력해주세요.")
            return
            
        # 서명 생성
        msg = f"{hwid}{app_name}{expiry}"
        signature = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
        
        license_data = {
            "hwid": hwid,
            "app_name": app_name,
            "expiry_date": expiry,
            "signature": signature
        }
        
        try:
            save_path = "license.lic"
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(license_data, f, indent=4, ensure_ascii=False)
            
            messagebox.showinfo("성공", f"라이센스 파일이 생성되었습니다!\n경로: {os.path.abspath(save_path)}")
        except Exception as e:
            messagebox.showerror("오류", f"파일 저장 중 오류 발생: {e}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    LicenseKeyGen().run()
