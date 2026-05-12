# Work Log - DS Capture

## 2026-05-12 (Tue)
### [v1.00.24] - 서브프로세스 기반 메모리 격리 및 드래그 성능 최적화
- **서브프로세스 기반 메모리 관리 아키텍처 도입**
    - **편집기 분리**: `ImageEditor` 클래스를 독립 스크립트(`DS_image_editor.py`)로 완전 분리.
    - **멀티 엔진 모드**: 단일 EXE 파일이 인자(`--editor`)에 따라 메인 앱 또는 편집기로 동작하는 기술 구현.
    - **RAM 100% 반환**: 편집기를 별도 프로세스로 띄움으로써, 편집기 종료 시 OS가 해당 메모리를 즉시 완벽하게 회수하도록 최적화.
- **드래그 캡처 성능 극대화**
    - **Input Lag 제거**: 자유 드래그 중 실시간 이미지 크롭 및 변환 로직을 제거하여, 마우스 커서와 가이드라인이 100% 동기화되도록 성능 최적화.
- **프로젝트 구조 및 빌드 시스템 고도화**
    - **자산 관리**: `DS_capture.ico`, `DS_capture.png`를 전용 `icon/` 폴더로 이동하여 프로젝트 구조화.
    - **빌드 속도 개선**: `build.py` 수정으로 테스트 빌드(`test`) 시에는 `--onedir` 방식을 사용하여 빌드 시간을 2배 이상 단축.
    - **코드 리팩토링**: `main_entry()` 통합 및 중복 경로 변수 제거로 유지보수성 향상.
- **Git 환경 최적화**: `.gitignore` 보강 및 빌드 임시 파일 저장소 정화 완료.


## 2026-05-11 (Mon)
### [v1.00.22] - Esc 키 동작 수정 및 배포 빌드
- **환경설정 창 Esc 종료 문제 수정**
    - `MainApp._on_esc_main`: Toplevel 창(`winfo_exists`, `winfo_viewable`)이 하나라도 활성화되어 있으면 메인 창이 닫히지 않도록 보호 로직 추가.
    - `MainApp.open_settings_window`: `pop.bind("<Escape>")` 핸들러에서 `return "break"`를 반환하여 부모 윈도우로의 이벤트 전파를 차단하고 `pop.focus_force()` 추가.
- **하위 윈도우 Esc 핸들링 표준화**
    - `ResizableBox`: `_on_esc_box` 메서드 신설 및 `bind("<Escape>")`를 통해 안전한 종료와 `return "break"` 처리.
    - `MainApp.start_drag`: 드래그 캡처 오버레이(`ov`)에 `_on_esc_ov` 로직을 추가하여 Esc 입력 시 안전하게 종료되도록 수정.
    - `MainApp.popup_shortcut_settings`: 단축키 설정 Toplevel 창에 Esc 바인딩 누락분 추가.
- **배포 빌드 실행**: `build.py`를 실행하여 v1.00.22 단일 실행 파일 빌드 완료 (`dist_production/DS Capture.exe`).

### [v1.00.21] - 아이콘 브랜딩 및 이미지 편집기 고도화
- **아이콘 및 브랜드 통합**
    - **AppUserModelID 강제 설정**: `ctypes`를 통해 `SetCurrentProcessExplicitAppUserModelID`를 호출하여 작업표시줄 아이콘 그룹화 및 고정 아이콘 불일치 문제 해결.
    - **전역 아이콘 적용**: `set_window_icon` 함수를 통해 메인 윈도우, Toplevel, 메세지 박스 등 모든 창에 `DS_capture.ico` 일괄 적용.
    - **트레이 아이콘 최적화**: `pystray` 아이콘 생성 시 이미지의 투명 여백을 자동으로 크롭(`getbbox`)하여 트레이 영역에서 아이콘이 더 크게 보이도록 개선.
- **이미지 편집기 (`ImageEditor`) 기능 강화**
    - **도구 상태 관리**: 형광펜(`highlight`) 도구 선택 시 이전 선 두께와 색상을 저장하고, 다른 도구로 변경 시 원복하는 스마트 전환 로직 구현.
    - **그리기 미리보기 최적화**: 캔버스 배율(`scale`)에 따른 선 굵기 미리보기를 실제 저장될 굵기와 동기화.
    - **UI 개선**: 툴바 레이아웃 최적화 및 폰트 설정(맑은 고딕), 색상 팔레트 시인성 개선.
- **전역 Esc 단축키 도입**: `MainApp`, `ImageEditor`, `ResizableBox` 등 주요 클래스에 `bind("<Escape>")` 적용 및 `_on_esc_main` 기초 설계.
- **빌드 자동화 시스템**: `build.py` 내에 `BUILD_VERSION`, `BUILD_DATE`, `BUILD_TIME`을 소스 코드에 자동 주입하는 regex 로직 구현.

## 2026-05-08 (Fri) ~ 2026-05-11 (Mon)
### [v1.00.15] - 빌드 시스템 전환 및 안정화 (Commit: 84f1338 이후)
- **빌드 도구 전환 (Nuitka → PyInstaller)**
    - Python 3.14 환경에서의 Nuitka 컴파일 불안정성으로 인해 **PyInstaller**로 빌드 시스템 전격 교체.
    - `build.py`: `TEST`(--onedir) 및 `PRODUCTION`(--onefile) 모드 지원 및 빌드 아티팩트 자동 정리 기능 구현.
- **보안 및 실행 안정성 강화**
    - **중복 실행 방지**: Windows Mutex(`CreateMutexW`)를 이용한 `enforce_single_instance` 로직 구현.
    - **HWID 동기화**: C# 기반 라이센스 체커와의 호환성을 위해 HWID 생성 로직 최적화 및 서명 검증 방식 일원화.
- **DPI 고해상도 대응**: `SetProcessDpiAwareness`를 통한 고해상도 모니터 폰트 흐림 현상 해결.
- **프로젝트 구조 정리**: `DS Capture.py` → `DS_capture.py`로 파일명 변경 및 관련 리소스 경로 재설정.
