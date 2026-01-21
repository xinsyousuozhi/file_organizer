# 파일 정리 도구 (File Organizer)

로컬 파일을 체계적으로 정리하는 Python 기반 도구입니다.

## 주요 기능

1. **중복 파일 처리** - SHA256 해싱 기반 정확한 중복 탐지
2. **버전 파일 그룹화** - 유사한 파일명(v1, v2, 최종, final 등) 그룹화
3. **스마트 파일 분류** - 4가지 분류 모드 지원
   - 🚀 **확장자 기반**: 빠른 정리 (대량 파일)
   - ⭐ **Gemini CLI**: 문서 내용 기반 LLM 분류 (설정 간편) **추천**
   - 🤖 **LLM API**: 내용 분석 (Claude, OpenAI, Gemini API)
   - 🎯 **Claude Code**: 실시간 협업 분류 ([가이드](./CLAUDE_CODE_MODE.md))
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

# LLM으로 문서 파일 분류 (Gemini CLI 사용) ⭐
python main.py ~/Downloads --llm gemini-cli --execute
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

## 🎯 파일 분류 모드 선택 가이드

### 언제 어떤 모드를 사용할까?

| 상황 | 추천 모드 | 이유 |
|------|-----------|------|
| 단순히 확장자별로만 정리 | 🚀 확장자 기반 | 가장 빠름 |
| 문서 파일 내용 기반 분류 | ⭐ **Gemini CLI** | 설정 간편, 무료 |
| API 키 있고 정확도 중시 | 🤖 LLM API | 높은 정확도 |
| 복잡한 분류 규칙 필요 | 🎯 Claude Code | 유연한 맞춤 분류 |
| 프로젝트별 정리 | 🎯 Claude Code | 컨텍스트 이해 |

### 📖 자세한 가이드

- **Gemini CLI 사용법**: 아래 "LLM 설정 가이드" → "Gemini CLI" 섹션 참고
- **Claude Code 사용법**: [CLAUDE_CODE_MODE.md](./CLAUDE_CODE_MODE.md)
- **LLM API 설정**: 아래 "LLM 설정 가이드" 섹션 참고
- **성능 최적화**: 아래 "성능 최적화 가이드" 섹션 참고

## 주의사항

1. **첫 실행은 반드시 드라이 런 모드로** - `--execute` 없이 실행하여 미리보기
2. **제외 폴더 확인** - 중요한 프로젝트 폴더는 제외 목록에 추가
3. **백업 권장** - 중요한 파일은 미리 백업
4. **대량 파일 분류**: 50개 이상 파일은 Claude Code 사용 권장

---

## LLM 설정 가이드

### 지원하는 LLM 제공자

#### 1. Gemini CLI (추천) ⭐

**가장 간단한 LLM 분류 방법** - API 키 설정 없이 바로 사용 가능

##### 설치

```bash
# npm으로 설치
npm install -g @anthropic-ai/gemini-cli

# 또는 npx로 직접 실행 (설치 불필요)
npx @anthropic-ai/gemini-cli
```

##### 첫 실행 시 인증

```bash
# 처음 실행하면 브라우저에서 Google 계정 인증
gemini
```

##### CLI에서 사용

```bash
# 문서 파일만 LLM으로 분류 (이미지는 확장자 기반)
python main.py ~/Downloads --llm gemini-cli --execute

# 특정 모델 지정
python main.py ~/Downloads --llm gemini-cli --llm-model gemini-2.0-flash --execute

# 미리보기 (실제 실행 안함)
python main.py ~/Downloads --llm gemini-cli
```

##### 특징

- ✅ **API 키 불필요** - Google 계정 인증만으로 사용
- ✅ **무료 사용량** 제공
- ✅ **배치 처리** - 20개 파일씩 한 번에 처리하여 빠름
- ✅ **문서 전용** - PDF, HWP, DOC 등 문서 파일만 LLM 분류
- ✅ **PDF 내용 분석** - PDF 텍스트 추출 후 LLM 분류
- ⚠️ **바이너리 문서** - HWP, DOC, DOCX는 파일명만 분류에 사용

##### 지원 모델

| 모델 | 설명 | 용도 |
|------|------|------|
| `gemini-2.0-flash` | 최신 빠른 모델 (기본값) | 일반 사용 |
| `gemini-1.5-pro` | 고급 모델 | 복잡한 분류 |
| `gemini-1.5-flash` | 빠른 모델 | 대량 파일 |

##### 배치 처리 동작

```
문서 100개 파일 분류:
├── PDF 파일 → 내용 추출 후 LLM 분류
├── HWP/DOC 파일 → 파일명으로 LLM 분류
├── TXT/MD 파일 → 내용 추출 후 LLM 분류
└── 20개씩 배치로 LLM 호출 (총 5회 호출)

이미지 파일:
└── 확장자 기반 분류 (LLM 미사용, 빠름)
```

---

#### 2. Claude (Anthropic)
```python
from src.llm_classifier import LLMConfig

llm_config = LLMConfig(
    provider="claude",
    api_key="sk-ant-api03-...",  # 또는 환경변수 ANTHROPIC_API_KEY
    model="claude-3-5-sonnet-20241022",
    temperature=0.3,
    max_tokens=500
)
```

#### 2. OpenAI GPT
```python
llm_config = LLMConfig(
    provider="openai",
    api_key="sk-...",  # 또는 환경변수 OPENAI_API_KEY
    model="gpt-4o-mini",
    temperature=0.3,
    max_tokens=500
)
```

#### 3. Google Gemini
```python
llm_config = LLMConfig(
    provider="gemini",
    api_key="AIza...",  # 또는 환경변수 GOOGLE_API_KEY
    model="gemini-1.5-flash",
    temperature=0.3,
    max_tokens=500
)
```

#### 5. Ollama (로컬 LLM)
```python
llm_config = LLMConfig(
    provider="ollama",
    model="llama3.2",
    base_url="http://localhost:11434",
    temperature=0.3,
    max_tokens=500
)
```

#### 6. 키워드 기반 분류 (LLM 없이)
```python
llm_config = LLMConfig(provider="none")
# 또는
llm_config = None
```

### 환경변수로 API 키 설정 (권장)

#### Windows (PowerShell)
```powershell
# 현재 세션
$env:ANTHROPIC_API_KEY="sk-ant-api03-..."
$env:OPENAI_API_KEY="sk-..."
$env:GOOGLE_API_KEY="AIza..."

# 영구 설정
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-api03-...", "User")
```

#### Linux/Mac
```bash
# ~/.bashrc 또는 ~/.zshrc에 추가
export ANTHROPIC_API_KEY="sk-ant-api03-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="AIza..."
```

### 필요한 패키지 설치

```bash
# Claude
pip install anthropic

# OpenAI
pip install openai

# Gemini
pip install google-generativeai

# Ollama (별도 설치 필요)
# https://ollama.ai/download
```

### 추천 설정

#### 높은 정확도가 필요한 경우
```python
llm_config = LLMConfig(
    provider="claude",
    model="claude-3-5-sonnet-20241022",
    temperature=0.2  # 더 일관된 결과
)
```

#### 빠른 처리가 필요한 경우
```python
llm_config = LLMConfig(
    provider="gemini",
    model="gemini-1.5-flash",
    temperature=0.3
)
```

#### 비용 절감 (로컬)
```python
llm_config = LLMConfig(
    provider="ollama",
    model="llama3.2",
    temperature=0.3
)
```

---

## 성능 최적화 가이드

### 느려지는 주요 원인과 해결책

#### 🐌 LLM 분류 사용 시
**증상**: 파일 분류 단계에서 매우 느림 (파일당 1-5초)

**원인**: 각 파일마다 LLM API 호출

**해결책**:
1. **LLM 비활성화**
   - GUI → 🤖 LLM 설정 → "none (키워드 기반)" 선택
   - 10-100배 빠름

2. **빠른 LLM 모델 사용**
   - Gemini Flash: `gemini-1.5-flash`
   - Ollama 로컬: `llama3.2` (빠르고 무료)

3. **분류 파일 수 제한**
   - 50개 이상 파일은 자동으로 키워드 기반으로 전환
   - 특정 확장자만 분류
   - 제외 폴더 활용

### ⚡ 성능 비교

| 작업 | LLM 사용 | 키워드 기반 | 속도 차이 |
|------|---------|------------|-----------|
| 파일 100개 분류 | 5-10분 | 1-5초 | 100배 |
| 중복 파일 탐지 | 동일 | 동일 | 차이 없음 |
| 파일 스캔 | 동일 | 동일 | 차이 없음 |

### 💡 추천 설정

#### 빠른 정리 (일상적 사용)
```
LLM: none (키워드 기반)
분류: ✓
중복 처리: ✓
```
→ **100개 파일: 5초**

#### 정확한 분류 (가끔)
```
LLM: gemini-1.5-flash
분류: ✓
중복 처리: ✓
```
→ **100개 파일: 2-3분**

#### 최고 정확도 (중요 정리)
```
LLM: claude-3-5-sonnet-20241022
분류: ✓
중복 처리: ✓
```
→ **100개 파일: 5-10분**

### 🔧 최적화 팁

1. **제외 폴더 설정**
   - node_modules, .git 등 불필요한 폴더 제외
   - 대용량 폴더 제외

2. **파일 수 줄이기**
   - 특정 폴더만 선택
   - 작은 폴더부터 테스트

3. **파일 수 제한**
   - LLM 분류는 50개 이하로 자동 제한
   - 초과 시 키워드 기반으로 자동 전환

### ⚠️ 현재 제한사항

- LLM 분류는 순차 처리 (파일 하나씩)
- 텍스트 파일만 LLM 사용 (5MB 이하)
- 이미지, 비디오는 키워드 기반

### 📊 실시간 로그 확인

실행 중 로그를 보면 어느 단계가 느린지 확인 가능:
```
[1단계] 파일 스캔...         # 빠름 (수 초)
[2단계] 중복 파일 탐지...     # 보통 (1-30초)
[3단계] 버전 파일 탐지...     # 빠름 (수 초)
[4단계] 문서/이미지 분류...   # 느림 (LLM 사용 시)
  📡 LLM 분류 활성화: ollama
  ⚠️ LLM 분류는 시간이 오래 걸릴 수 있습니다...
```

### 🚀 빠른 진단

**느린 경우**:
1. LLM 설정 확인 → "none"으로 변경
2. 제외 폴더 확인 → 대용량 폴더 제외
3. 대상 폴더 크기 확인 → 작은 폴더로 테스트

**정상 속도**:
- 1000개 파일: 10-30초 (키워드 기반)
- 100개 파일: 1-5초 (키워드 기반)

### LLM 제공자별 성능 비교

| 제공자 | 속도 | 정확도 | 비용 | 설정 난이도 |
|--------|------|--------|------|-------------|
| **Gemini CLI** ⭐ | 빠름 | 높음 | 무료 | 쉬움 |
| Claude | 빠름 | 매우 높음 | 중간 | 중간 |
| OpenAI | 빠름 | 높음 | 중간 | 중간 |
| Gemini API | 매우 빠름 | 높음 | 낮음 | 중간 |
| Ollama | 중간 | 중간 | 무료 | 어려움 |
| 키워드 | 매우 빠름 | 낮음 | 무료 | 없음 |

> **추천**: 처음 사용자는 **Gemini CLI**로 시작하세요. API 키 설정 없이 바로 사용 가능합니다.

---

## 라이센스

MIT License
