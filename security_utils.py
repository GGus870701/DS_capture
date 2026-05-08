import subprocess
import hashlib
import os
import sys

def get_hwid():
    """
    기기 고유 정보를 조합하여 해싱된 HWID 생성
    1. 메인보드 시리얼
    2. 디스크 시리얼 (C: 드라이브)
    """
    try:
        # 1. 메인보드 시리얼 추출
        cmd_mb = "wmic baseboard get serialnumber"
        mb_serial = subprocess.check_output(cmd_mb, shell=True).decode().split('\n')[1].strip()
        
        # 2. 디스크 시리얼 추출
        cmd_disk = "wmic diskdrive get serialnumber"
        disk_serial = subprocess.check_output(cmd_disk, shell=True).decode().split('\n')[1].strip()
        
        # 정보 조합
        raw_id = f"DS_{mb_serial}_{disk_serial}"
        
        # SHA256 해싱 후 앞 12자리 추출 (사용자 편의성)
        hash_id = hashlib.sha256(raw_id.encode()).hexdigest().upper()
        formatted_id = f"{hash_id[:4]}-{hash_id[4:8]}-{hash_id[8:12]}"
        
        return formatted_id
    except Exception as e:
        return f"ERROR-{hash(str(e)) % 10000}"

if __name__ == "__main__":
    print(f"Current HWID: {get_hwid()}")
