import os
import re
import subprocess
import sys
import datetime

def main():
    py_file = 'DS Capture.py'
    
    # 1. DS Capture.py 읽기
    if not os.path.exists(py_file):
        print(f"Error: {py_file} 파일을 찾을 수 없습니다.")
        return

    with open(py_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 2. 현재 버전 정보 찾기 (BUILD_VERSION = "v1.xx" 형식)
    match = re.search(r'BUILD_VERSION = "v1\.(\d+)"', content)
    if not match:
        print("버전 정보를 BUILD_VERSION 변수에서 찾을 수 없습니다.")
        return

    current_minor = int(match.group(1))
    new_minor = current_minor + 1
    new_version = f"v1.{new_minor:02d}"
    
    # 3. 현재 날짜 및 시간 가져오기
    now = datetime.datetime.now()
    new_date = now.strftime("%Y-%m-%d")
    new_time = now.strftime("%H:%M:%S")
    
    print(f"새 빌드 정보 생성: Version={new_version}, Date={new_date}, Time={new_time}")

    # 4. 소스 코드 내 빌드 정보 업데이트
    new_content = re.sub(r'BUILD_VERSION = ".*?"', f'BUILD_VERSION = "{new_version}"', content, count=1)
    new_content = re.sub(r'BUILD_DATE = ".*?"', f'BUILD_DATE = "{new_date}"', new_content, count=1)
    new_content = re.sub(r'BUILD_TIME = ".*?"', f'BUILD_TIME = "{new_time}"', new_content, count=1)
    
    with open(py_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    print(f"DS Capture.py 빌드 정보 업데이트 완료.")
    
    # 5. Nuitka로 패키징 실행
    cpu_jobs = os.cpu_count() or 1  # 논리 코어 수 자동 감지
    print(f"[{new_version}] Nuitka 컴파일을 시작합니다... (병렬 작업: {cpu_jobs}개)")
    
    # 빌드 시간 측정을 위한 시작 시간
    start_time = datetime.datetime.now()
    
    # 캐시 디렉토리 설정 (속도 향상의 핵심)
    cache_dir = os.path.join(os.path.expanduser("~"), ".nuitka_cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    
    # 환경 변수 설정
    env = os.environ.copy()
    env["NUITKA_CACHE_DIR"] = cache_dir
    
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        f"--jobs={cpu_jobs}",                    # CPU 코어 병렬 활용
        "--windows-console-mode=disable",
        "--enable-plugin=tk-inter",
        "--enable-plugin=anti-bloat",            # 불필요한 모듈 제거
        "--noinclude-pytest-mode=nofollow",
        "--noinclude-setuptools-mode=nofollow",
        "--noinclude-unittest-mode=nofollow",
        "--windows-icon-from-ico=icon.ico",
        "--include-data-files=icon.ico=icon.ico",
        "--assume-yes-for-downloads",
        "--output-dir=dist_production",
        "--output-filename=DS Capture.exe",
        py_file
    ]
    
    # 64비트 최적화 및 캐시 활성화를 위한 추가 인자 (필요시)
    # cmd.append("--lto=yes") # 속도는 약간 느려지나 결과물 성능 향상. 일단은 제외.

    result = subprocess.run(cmd, env=env)
    
    # 빌드 시간 측정 종료
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    minutes, seconds = divmod(duration.seconds, 60)
    
    if result.returncode == 0:
        print(f"\n[SUCCESS] 패키징이 성공적으로 완료되었습니다!")
        print(f"결과물: dist_production/DS Capture.exe")
        print(f"총 소요 시간: {minutes}분 {seconds}초")
        
        # 6. 임시 파일 정리
        print("\n임시 빌드 파일을 정리하는 중...")
        import shutil
        base_path = "dist_production"
        dummy_folders = [
            os.path.join(base_path, "DS Capture.build"),
            os.path.join(base_path, "DS Capture.onefile-build"),
            os.path.join(base_path, "DS Capture.dist")
        ]
        
        for folder in dummy_folders:
            if os.path.exists(folder):
                try:
                    shutil.rmtree(folder)
                except:
                    pass
        print("정리 완료.")
    else:
        print(f"\n[ERROR] 패키징 중 오류가 발생했습니다. (소요 시간: {minutes}분 {seconds}초)")

if __name__ == "__main__":
    main()
