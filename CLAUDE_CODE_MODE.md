# 🤖 Claude Code로 정확한 파일 분류하기

## 왜 Claude Code를 사용하나요?

### 📊 분류 방식 비교

| 방식 | 속도 | 정확도 | 적합한 경우 |
|------|------|--------|-------------|
| **확장자 기반** | ⚡ 매우 빠름 | ⭐ 낮음 | 빠른 정리만 필요할 때 |
| **LLM 자동** | 🐌 느림 | ⭐⭐⭐ 높음 | 50개 이하 소량 파일 |
| **Claude Code** | ⚡ 빠름 | ⭐⭐⭐⭐⭐ 매우 높음 | 대량 파일, 정확한 분류 필요 |

### 💡 Claude Code의 장점

- ✅ **실시간 협업**: Claude AI가 파일 내용을 보고 실시간으로 분류
- ✅ **컨텍스트 이해**: 프로젝트 전체 구조 파악
- ✅ **유연한 분류**: 사용자 요구사항에 맞춤 분류
- ✅ **빠른 처리**: 대량 파일도 효율적으로 처리
- ✅ **대화형 수정**: 분류 결과를 즉시 조정 가능

---

## 🚀 사용 방법

### 1️⃣ Claude Code 설치

**VSCode Extension 설치 (권장)**
1. VSCode 실행
2. Extensions (Ctrl+Shift+X)
3. "Claude Code" 검색
4. Install
5. API 키 설정

### 2️⃣ 이 프로젝트에서 실행

```bash
# VSCode에서
1. 이 file_organizer 프로젝트 폴더 열기
2. Ctrl+Shift+P → "Claude Code: Start"
3. Claude에게 요청
```

### 3️⃣ Claude에게 파일 정리 요청

**중요**: 별도 스크립트를 작성하는 게 아니라, **이 프로젝트를 Claude가 실행**합니다!

```
이 file_organizer 프로젝트를 실행해서 ~/Downloads를 정리해줘.

규칙:
- 송장은 "재무/송장" 폴더로
- 계약서는 "법무/계약" 폴더로
- 사진은 연도별로 정리
- 중복 파일은 최신 것만 남기기
```

### 4️⃣ Claude가 자동으로

1. ✅ 이 프로젝트의 `main.py` 실행
2. ✅ 설정 파일(config.yaml) 자동 생성
3. ✅ 파일 스캔 및 내용 분석
4. ✅ 미리보기 제공
5. ✅ 승인 후 실제 실행
6. ✅ 결과 보고

---

## 📝 사용 예시

### 예시 1: 업무 문서 정리

```
file_organizer로 Downloads 폴더의 문서를 정리해줘.

- PDF 송장은 "재무/송장/2024"로
- 계약서는 "법무/계약"으로
- 보고서는 "업무/보고서"로
- 중복 제거하고
- 빈 폴더도 정리해줘
```

### 예시 2: 사진 정리

```
file_organizer GUI를 열어서 미리보기 먼저 보여줘.

그리고 사진을:
1. 스크린샷은 "스크린샷" 폴더로
2. 가족 사진은 "사진/가족"으로
3. 여행 사진은 "사진/여행"으로 분류해줘
```

### 예시 3: 논문 PDF 정리

```
Downloads의 논문 PDF들을 정리해줘.

- 주제별로 분류
- 논문 제목으로 파일명 변경
- 저자별 하위 폴더 생성
- config.yaml에 papers.enabled: true로 설정해서 실행
```

---

## 🎯 고급 활용

### 맞춤 설정 파일 생성 요청

```
다음 규칙으로 config.yaml을 만들어줘:

1. 대상: ~/Downloads, ~/Documents/Unsorted
2. LLM: ollama (qwen3)
3. 제외 폴더: my_project, important_files
4. 중복 처리: newest
5. 월별 폴더 생성
```

Claude가 `config.yaml` 생성 후 → `python main.py --config config.yaml --execute`

### 미분류 파일만 재정리

```
Organized 폴더에서 루트에 있는 미분류 파일만 찾아서
기존 카테고리에 맞게 재정리해줘.
```

Claude가:
1. `UnorganizedFinder`로 루트 파일 검색
2. 기존 카테고리 분석
3. 적합한 폴더로 자동 분류

---

## 🆚 일반 실행 vs Claude Code

### 일반 실행 (GUI/CLI)

```bash
# 직접 실행
python main.py ~/Downloads --execute

# 한계
- 고정된 분류 규칙
- 특정 파일 예외 처리 어려움
- 결과 수정 번거로움
```

### Claude Code로 실행

```
# Claude에게 요청
file_organizer로 Downloads를 정리하되,
"중요" 폴더와 "프로젝트A"는 건드리지 마.

# Claude가:
1. 제외 폴더 설정에 추가
2. 실행
3. 결과 보고

# 결과 확인 후 조정
PDF만 다시 "문서/PDF"로 재분류해줘
```

**차이점**: Claude가 코드를 **읽고, 이해하고, 실행**합니다!

---

## 💻 설치 및 설정

### VSCode Extension (권장)

1. VSCode에서 Extensions 열기
2. "Claude Code" 검색
3. Install
4. API 키 설정 (Settings에서)

### 프로젝트 준비

```bash
cd file_organizer
pip install -r requirements.txt  # 의존성 설치
```

---

## 🆚 언제 무엇을 사용할까?

### ⚡ 확장자 기반 (GUI/CLI 직접 실행)
- 단순 정리만 필요
- 파일 1000개 이상
- 분류 정확도 중요하지 않음

### 🤖 LLM 자동 (GUI/CLI 직접 실행)
- 파일 50개 이하
- 한 번만 사용
- 기본 분류로 충분

### 🎯 Claude Code (강력 추천)
- 파일 50개 이상
- 복잡한 분류 규칙
- 프로젝트별 맞춤 정리
- 결과 확인 후 즉시 조정
- 반복 사용 (설정 저장)

---

## 🙋 자주 묻는 질문

**Q: Claude Code가 새로운 스크립트를 작성하나요?**
A: 아니요! **이 프로젝트의 기존 코드를 실행**합니다. 필요하면 `config.yaml` 생성 정도만 합니다.

**Q: 파일이 삭제되나요?**
A: 아니요. 모두 아카이브 폴더로 이동되며, 드라이 런으로 미리 확인 가능합니다.

**Q: 비용이 발생하나요?**
A: Claude API 사용량에 따라 과금됩니다. 파일 정리는 소량 비용만 발생합니다.

**Q: 한국어로 대화 가능한가요?**
A: 네, Claude는 한국어를 완벽하게 지원합니다.

---

**💡 Tip**: "file_organizer로 ... 해줘" 형태로 요청하면 Claude가 이 프로젝트를 실행합니다!
