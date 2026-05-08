import tkinter as tk
from tkinter import messagebox
from security_utils import get_hwid

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
