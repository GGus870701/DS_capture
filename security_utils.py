import subprocess
import hashlib
import os
import sys

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

if __name__ == "__main__":
    print(f"Current HWID: {get_hwid()}")
