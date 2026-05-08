import os
import re
import subprocess

def main():
    py_file = 'capture.py'
    
    # 1. capture.py 에서 현재 버전 찾기
    with open(py_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 정규식으로 'DS Capture v1.xx' 형태의 문자열 검색
    match = re.search(r'self\.root\.title\("DS Capture v1\.(\d+)"\)', content)
    
    if not match:
        print("버전 정보를 capture.py에서 찾을 수 없습니다.")
        return

    current_minor = int(match.group(1))
    new_minor = current_minor + 1
    new_version_str = f"1.{new_minor:02d}"
    
    # 2. capture.py 의 윈도우 타이틀 버전 업데이트
    old_title = f'DS Capture v1.{current_minor:02d}'
    new_title = f'DS Capture v{new_version_str}'
    new_content = content.replace(old_title, new_title)
    
    with open(py_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    print(f"버전 업데이트 완료: {old_title} -> {new_title}")
    
    # 3. PyInstaller로 패키징 실행
    print(f"[{new_title}] 패키징을 시작합니다...")
    
    import sys
    # 가상환경 또는 시스템의 pyinstaller 명령어
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", 
        "--clean", 
        "--onefile", 
        "--windowed", 
        "--icon=icon.ico", 
        "--add-data", "icon.ico;.", 
        "--name", "DS Capture", 
        "capture.py"
    ]
    
    # 명령어 실행
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n[SUCCESS] 패키징이 성공적으로 완료되었습니다!")
        print(f"결과물: dist/DS Capture.exe (내부 표기버전: {new_title})")
    else:
        print("\n[ERROR] 패키징 중 오류가 발생했습니다.")

if __name__ == "__main__":
    main()
