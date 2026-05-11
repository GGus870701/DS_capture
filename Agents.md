# DS Capture Agent Guidelines

이 파일은 AI 에이전트가 DS Capture 프로젝트를 작업할 때 참고해야 할 필수 환경 정보와 지침을 담고 있습니다.

## 1. 환경 정보 (Environment)
> [!IMPORTANT]
> Python 3.14 실험적 버전 사용으로 인해 **PyInstaller**를 주력 빌드 도구로 사용함 (Nuitka는 3.14에서 실행 오류 발생 가능성 높음).
- **Python Path**: `C:\Users\zars8\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- **Python Version**: 3.14.3
- **Build Tool**: PyInstaller 6.20.0 이상

## 2. 프로젝트 아키텍처 (Architecture)
- **Main Script**: `DS Capture.py`
- **Build Script**: `build.py` (PyInstaller 기반 버전)
- **Licensing**: HWID 기반 오프라인 라이센스 시스템
    - **절대 경로**: `C:\license` (가장 먼저 탐색하며 반드시 인식해야 함)
    - **상대 경로**: 실행 폴더 내 `license` 폴더 및 실행 파일 바로 옆
- **Configuration**: `settings.json` (실행 폴더 내 저장)

## 3. 빌드 지침 (Build Instructions)
- **빌드 도구**: PyInstaller
- **빌드 모드**:
    - **PRODUCTION**: `--onefile --windowed` (단일 EXE, 콘솔 숨김, 무압축)
    - **TEST**: `--onedir --console` (폴더 형태, 콘솔 표시, 빠른 빌드)
- **아이콘**: `DS_capture.ico` 필수 포함

## 4. 작업 시 주의사항 (Important Notes)
- **라이센스 인식**: `C:\license`는 프로그램이 어떤 경로에서 실행되더라도 항상 참조해야 하는 절대 경로임.
- **빌드 정보 업데이트**: `DS Capture.py`의 빌드 버전/날짜/시간은 `build.py` 실행 시 자동 갱신됨.
- **DPI 인식**: `ctypes`를 이용한 DPI Awareness 설정이 되어 있어 고해상도 모니터에서도 텍스트가 선명하게 표시됨.

## 5. UI/UX 및 아이콘 지침 (UI/UX & Icons)
- **작업표시줄 그룹화**: `AppUserModelID`를 `'ds.capture.v1.0'`으로 설정.
- **아이콘 설정**: 모든 서브 윈도우(`ResizableBox`, `ImageEditor` 등)에 `iconbitmap()`을 명시적으로 지정하여 깃털 아이콘이 표시되지 않도록 함.

## 6. 빌드 실행 방법
```powershell
# 1. 테스트 빌드 (폴더 실행 방식, dist_test 폴더 생성)
python build.py test

# 2. 배포 빌드 (단일 EXE 파일 생성, dist_production 폴더 생성)
python build.py
```
