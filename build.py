import os
import re
import subprocess
import sys
import datetime
import shutil

def main():
    py_file = 'DS Capture.py'
    output_dir = 'dist_production'
    test_dir = 'dist_test'
    
    # 1. 파일 존재 확인
    if not os.path.exists(py_file):
        print(f"Error: {py_file} 파일을 찾을 수 없습니다.")
        return

    # 2. 버전 정보 및 빌드 정보 업데이트
    with open(py_file, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.search(r'BUILD_VERSION = "(\d+)\.(\d+)\.(\d+)"', content)
    if not match:
        print("버전 정보를 찾을 수 없습니다. (1.00.00 형식 필요)")
        return

    major, minor, patch = match.group(1), match.group(2), int(match.group(3))
    
    # 테스트 빌드인지 배포 빌드인지 확인
    is_test = len(sys.argv) > 1 and sys.argv[1].lower() == 'test'
    
    if is_test:
        mode_str = "TEST"
        target_dir = test_dir
        new_version = f"{major}.{minor}.{patch:02d}" # 테스트는 버전 유지
    else:
        mode_str = "PRODUCTION"
        target_dir = output_dir
        new_version = f"{major}.{minor}.{patch + 1:02d}" # 배포는 버전 업
    
    now = datetime.datetime.now()
    new_date = now.strftime("%Y-%m-%d")
    new_time = now.strftime("%H:%M:%S")
    
    print(f"\n=== [{mode_str} BUILD] Version={new_version} ===")
    
    # 소스 코드 업데이트 (배포 시에만)
    if not is_test:
        new_content = re.sub(r'BUILD_VERSION = ".*?"', f'BUILD_VERSION = "{new_version}"', content, count=1)
        new_content = re.sub(r'BUILD_DATE = ".*?"', f'BUILD_DATE = "{new_date}"', new_content, count=1)
        new_content = re.sub(r'BUILD_TIME = ".*?"', f'BUILD_TIME = "{new_time}"', new_content, count=1)
        with open(py_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("빌드 정보 업데이트 완료.")

    # 3. PyInstaller 명령어 구성
    print(f"PyInstaller 패키징을 시작합니다...")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        f"--workpath=build_{mode_str.lower()}",
        f"--specpath=.",
    ]
    
    if is_test:
        # 테스트 빌드: 폴더 형태, 콘솔 창 표시
        cmd.extend(["--onedir", "--console"])
        dist_path = os.path.join(test_dir, "DS Capture")
    else:
        # 배포 빌드: 단일 파일, 콘솔 창 숨김
        cmd.extend(["--onefile", "--windowed"])
        dist_path = os.path.join(output_dir, "DS Capture.exe")

    # 공통 옵션
    cmd.extend([
        "--icon=DS_capture.ico",
        f"--name=DS Capture",
        f"--distpath={target_dir}",
        py_file
    ])

    # 4. 실행
    start_time = datetime.datetime.now()
    result = subprocess.run(cmd)
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    
    if result.returncode == 0:
        print(f"\n[SUCCESS] {mode_str} 빌드 완료!")
        print(f"위치: {target_dir}")
        print(f"소요 시간: {duration.seconds // 60}분 {duration.seconds % 60}초")
        
        # 임시 파일 정리 (배포 빌드 시에만)
        if not is_test:
            print("임시 파일 정리 중...")
            if os.path.exists('DS Capture.spec'): os.remove('DS Capture.spec')
            shutil.rmtree(f'build_{mode_str.lower()}', ignore_errors=True)
    else:
        print(f"\n[ERROR] {mode_str} 빌드 실패.")

if __name__ == "__main__":
    main()
