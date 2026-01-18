# 파일 정리 도구 (File Organizer)

로컬 파일을 체계적으로 정리하는 Python 기반 도구입니다.

## 주요 기능

1. **중복 파일 처리** - SHA256 해싱 기반 정확한 중복 탐지
2. **버전 파일 그룹화** - 유사한 파일명(v1, v2, 최종, final 등) 그룹화
3. **주제별 분류** - 문서/이미지 파일을 키워드 기반으로 분류
4. **날짜별 정리** - 연도/월별 폴더 자동 생성
5. **빈 폴더 정리** - 파일 이동 후 남은 빈 폴더 삭제
6. **파일 정리 미리보기** - 실행 전 파일이 어떻게 재배치될지 확인
7. **제외 폴더 설정** - GUI에서 동적으로 제외 폴더 추가/제거
8. **안전한 처리** - 드라이 런 모드, 영구 삭제 없음, 복원 가능

## 설치

```bash
# 저장소 복사
cd file_organizer

# 의존성 설치 (선택사항 - 표준 라이브러리만 사용)
pip install -r requirements.txt
```

## 사용법

### CLI 사용

```bash
# 기본 실행 (미리보기)
python main.py ~/Downloads

# 실제 실행
python main.py ~/Downloads --execute

# 특정 폴더 제외
python main.py ~/Downloads --exclude "my_project" "data" --execute

# 월별 폴더까지 생성
python main.py ~/Downloads --with-month --execute
```

### GUI 사용

```bash
python main.py --gui
```

**GUI 주요 기능:**
- 📁 **폴더 설정**: 대상 폴더와 저장 폴더 선택
- ⚙️ **제외 폴더 설정**: GUI에서 제외 폴더 동적으로 추가/제거
- 👁️ **미리보기**: 파일이 어떻게 재배치될지 확인
  - 분류 예정 파일 목록 (현재 위치 → 이동 예정 경로)
  - 중복 파일 그룹 분석
  - 종합 통계 및 절약 가능 용량
- ✅ **정리 옵션**: 중복 처리, 주제별 분류, 연도/월별 폴더 생성 등 설정
- 🎯 **실행 모드**: 미리보기(드라이 런) 또는 실제 실행 선택

### 파일 복원

```bash
# 복원 미리보기
python main.py --restore

# 실제 복원
python main.py --restore --execute
```

### 빈 폴더 정리

```bash
# 빈 폴더 찾기 (미리보기)
python main.py --cleanup-empty ~/Downloads

# 빈 폴더 삭제
python main.py --cleanup-empty ~/Downloads --execute
```

### 폴더 그룹화

```bash
# 대화형 폴더 그룹화
python main.py --folder-groups ~/Downloads

# 실제 실행
python main.py --folder-groups ~/Downloads --execute
```

## 프로젝트 구조

```
file_organizer/
├── main.py                 # 메인 진입점
├── requirements.txt        # 의존성
├── README.md
│
├── src/                    # 핵심 모듈
│   ├── __init__.py
│   ├── config.py          # 설정 클래스
│   ├── duplicate_finder.py # 중복 탐지
│   ├── version_manager.py  # 버전 관리
│   ├── classifier.py       # 파일 분류
│   ├── file_mover.py       # 파일 이동
│   ├── logger.py           # 로깅
│   └── organizer.py        # 통합 클래스
│
├── cli/                    # CLI 모듈
│   ├── __init__.py
│   ├── main_cli.py        # 메인 CLI
│   ├── restore.py         # 복원 도구
│   ├── folder_groups.py   # 폴더 그룹화
│   └── cleanup_empty.py   # 빈 폴더 정리
│
├── gui/                    # GUI 모듈
│   ├── __init__.py
│   └── main_gui.py        # tkinter GUI
│
└── examples/               # 사용 예제
    ├── example_usage.py
    └── custom_config_example.py
```

## 설정 옵션

### 제외 폴더

기본적으로 다음 폴더들이 제외됩니다:
- 시스템: `.git`, `__pycache__`, `node_modules`, `$RECYCLE.BIN`
- 개발: `.venv`, `.idea`, `.vscode`, `dist`, `build`
- 도구: `_OrganizedFiles`, `file_organizer`

### 분류 대상 확장자

**문서**: `.pdf`, `.doc`, `.docx`, `.hwp`, `.hwpx`, `.xls`, `.xlsx`, `.ppt`, `.pptx` 등

**이미지**: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.svg`, `.webp` 등

**압축**: `.zip`, `.rar`, `.7z`, `.tar`, `.gz` 등

### 맞춤 설정

`examples/custom_config_example.py`를 복사하여 본인의 환경에 맞게 수정하세요.

## 사용 예시

### Python API 사용

```python
from pathlib import Path
from src.config import OrganizerConfig
from src.organizer import FileOrganizer

# 설정 생성
config = OrganizerConfig(
    target_directories=[Path.home() / "Downloads"],
    archive_base=Path.home() / "_OrganizedFiles",
    dry_run=True,
)

# 정리 실행
organizer = FileOrganizer(config)
try:
    files = organizer.scan_directories()
    duplicates = organizer.find_duplicates()
    operations = organizer.plan_cleanup(duplicates=True)
    results = organizer.execute(dry_run=True)
finally:
    organizer.finalize()
```

## 로그 및 복원

- 모든 작업은 `~/_OrganizedFiles/logs/`에 기록됩니다
- JSON 로그 파일로 복원 가능
- 파일은 영구 삭제되지 않고 아카이브 폴더로 이동됩니다

## 주의사항

1. **첫 실행은 반드시 드라이 런 모드로** - `--execute` 없이 실행하여 미리보기
2. **제외 폴더 확인** - 중요한 프로젝트 폴더는 제외 목록에 추가
3. **백업 권장** - 중요한 파일은 미리 백업

## 라이센스

MIT License
