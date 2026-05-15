import os
import re
import subprocess
import sys
import datetime
import shutil

def main():
    py_file = 'DS_capture.py'
    output_dir = 'dist_production'
    test_dir = 'dist_test'
    
    # 1. 파일 존재 확인
    if not os.path.exists(py_file):
        print(f"Error: {py_file} 파일을 찾을 수 없습니다.")
        return

    # 환경 정보 동기화 (Agents.md 업데이트)
    agents_file = 'Agents.md'
    current_python = sys.executable
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    if os.path.exists(agents_file):
        try:
            with open(agents_file, 'r', encoding='utf-8') as f:
                agents_content = f.read()
            
            saved_path_match = re.search(r'- \*\*Python Path\*\*: `(.*?)`', agents_content)
            saved_ver_match = re.search(r'- \*\*Python Version\*\*: ([\d\.]+)', agents_content)
            
            saved_path = saved_path_match.group(1) if saved_path_match else ""
            saved_ver = saved_ver_match.group(1) if saved_ver_match else ""
            
            if current_python != saved_path or (saved_ver and not current_version.startswith(saved_ver)):
                print(f"환경 변화 감지: Agents.md를 업데이트합니다.")
                new_agents_content = agents_content
                if saved_path_match:
                    new_agents_content = new_agents_content.replace(f"- **Python Path**: `{saved_path}`", f"- **Python Path**: `{current_python}`")
                if saved_ver_match:
                    new_agents_content = new_agents_content.replace(f"- **Python Version**: {saved_ver}", f"- **Python Version**: {current_version}")
                
                with open(agents_file, 'w', encoding='utf-8') as f:
                    f.write(new_agents_content)
                print("Agents.md 동기화 완료.")
        except Exception as e:
            print(f"Agents.md 동기화 실패: {e}")

    # 2. 버전 정보 및 빌드 정보 업데이트 (core/utils.py 관리)
    utils_file = 'core/utils.py'
    if not os.path.exists(utils_file):
        print(f"Error: {utils_file} 파일을 찾을 수 없습니다.")
        return

    with open(utils_file, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.search(r'BUILD_VERSION = "(\d+)\.(\d+)\.(\d+)"', content)
    if not match:
        print("버전 정보를 찾을 수 없습니다. (core/utils.py 확인 필요)")
        return

    major, minor, patch = match.group(1), match.group(2), int(match.group(3))
    
    # 테스트 빌드인지 배포 빌드인지 확인
    is_test = len(sys.argv) > 1 and sys.argv[1].lower() == 'test'
    
    if is_test:
        mode_str = "TEST"
        target_dir = test_dir
        new_version = f"{major}.{minor}.{patch:02d}"
    else:
        mode_str = "PRODUCTION"
        target_dir = output_dir
        new_version = f"{major}.{minor}.{patch + 1:02d}"
    
    now = datetime.datetime.now()
    new_date = now.strftime("%Y-%m-%d")
    new_time = now.strftime("%H:%M:%S")
    
    print(f"\n=== [{mode_str} BUILD] Version={new_version} ===")
    
    # 소스 코드 업데이트
    if not is_test:
        new_content = re.sub(r'BUILD_VERSION = ".*?"', f'BUILD_VERSION = "{new_version}"', content, count=1)
        new_content = re.sub(r'BUILD_DATE = ".*?"', f'BUILD_DATE = "{new_date}"', new_content, count=1)
        new_content = re.sub(r'BUILD_TIME = ".*?"', f'BUILD_TIME = "{new_time}"', new_content, count=1)
        with open(utils_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("빌드 정보(core/utils.py) 업데이트 완료.")

    # 3. PyInstaller 명령어 구성
    print(f"PyInstaller 패키징을 시작합니다...")
    
    # 제외할 대형 모듈 리스트 (용량 최적화)
    excludes = [
        'numpy', 'matplotlib', 'pandas', 'scipy', 'PyQt5', 'PyQt6',
        'IPython', 'notebook', 'jedi', 'setuptools', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets', 'PySide6.Qt3DCore', 'PySide6.QtCharts'
    ]
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        f"--workpath=build_{mode_str.lower()}",
        f"--specpath=.",
        "--collect-submodules=PySide6.QtSvg", # SVG 렌더링에 필요
        "--collect-submodules=core",
        "--collect-submodules=ui",
        "--collect-submodules=modules",
    ]
    
    # Exclude 옵션 추가
    for ex in excludes:
        cmd.extend(["--exclude-module", ex])
    
    if is_test:
        cmd.extend(["--onedir", "--console"])
    else:
        # 배포 빌드도 이제 용량 문제로 onedir(폴더) 방식으로 변경
        cmd.extend(["--onedir", "--windowed"])

    # 공통 옵션
    cmd.extend([
        "--icon=icon/DS_capture.ico",
        "--add-data=icon/DS_capture.ico;icon",
        "--add-data=DASAN Technology Safety logo.png;.",
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
        # 빌드 시각 및 요일 정보 (기록용)
        build_time_full = end_time.strftime("%Y-%m-%d (%a) %H:%M:%S")
        print(f"\n[SUCCESS] {mode_str} 빌드 완료!")
        print(f"위치: {target_dir}")
        print(f"소요 시간: {duration.seconds // 60}분 {duration.seconds % 60}초")
        
        # walkthrough.md 업데이트 (배포 빌드 시에만)
        if not is_test:
            # 인자에서 작업 내용(desc) 추출
            desc = ""
            for i, arg in enumerate(sys.argv):
                if arg == "--desc" and i + 1 < len(sys.argv):
                    desc = sys.argv[i+1]
                    break
            
            update_walkthrough(new_version, build_time_full, desc)

        # 임시 파일 정리 및 압축 (배포 빌드 시에만)
        if not is_test:
            print("임시 파일 정리 중...")
            if os.path.exists('DS Capture.spec'): os.remove('DS Capture.spec')
            shutil.rmtree(f'build_{mode_str.lower()}', ignore_errors=True)
            
            # 결과 폴더 압축
            print("결과물 압축 중...")
            zip_name = f"DS_Capture_v{new_version}"
            zip_path = os.path.join(target_dir, zip_name)
            
            original_dir = os.path.join(target_dir, "DS Capture")
            versioned_dir = os.path.join(target_dir, zip_name)
            
            if os.path.exists(original_dir):
                if os.path.exists(versioned_dir): shutil.rmtree(versioned_dir)
                os.rename(original_dir, versioned_dir)
                shutil.make_archive(zip_path, 'zip', versioned_dir)
                shutil.rmtree(versioned_dir, ignore_errors=True)
                print(f"최종 결과물: {zip_path}.zip")
    else:
        print(f"\n[ERROR] {mode_str} 빌드 실패.")

def update_walkthrough(version, build_time_full, desc):
    """빌드 성공 시 walkthrough.md 파일에 작업 내역 기록"""
    walkthrough_file = 'walkthrough.md'
    if not os.path.exists(walkthrough_file):
        return

    try:
        # 날짜와 요일 분리 (예: 2026-05-15 (Fri) 19:48:00 -> 2026-05-15 (Fri))
        parts = build_time_full.split(' ')
        date_header = f"## {parts[0]} {parts[1]}"
        time_part = parts[2]
        
        # 작업 내용이 없으면 기본 문구 사용
        if not desc:
            desc = "- 신규 빌드 및 기능 최적화"

        with open(walkthrough_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 기존 날짜 헤더가 있는지 확인
        date_index = -1
        for i, line in enumerate(lines):
            if line.strip() == date_header:
                date_index = i
                break

        new_entry = [
            f"### [v{version}] - Build at {time_part}\n",
            f"{desc}\n\n"
        ]

        if date_index != -1:
            # 기존 날짜 헤더 아래에 새 버전 추가
            updated_content = lines[:date_index + 1] + ["\n"] + new_entry + lines[date_index + 1:]
        else:
            # 새로운 날짜 헤더와 함께 추가 (파일 헤더 바로 아래)
            updated_content = [lines[0], "\n", f"{date_header}\n"] + new_entry + lines[1:]
        
        with open(walkthrough_file, 'w', encoding='utf-8') as f:
            f.writelines(updated_content)
        print(f"walkthrough.md 업데이트 완료 (v{version})")
        
    except Exception as e:
        print(f"walkthrough.md 업데이트 실패: {e}")

if __name__ == "__main__":
    main()
