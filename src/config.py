"""
설정 모듈: 애플리케이션 전역 설정 및 상수 정의
"""

from pathlib import Path
from typing import List, Set
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class OrganizerConfig:
    """파일 정리 도구 설정 클래스"""

    # 정리 대상 폴더들
    target_directories: List[Path] = field(default_factory=list)

    # 아카이브 기본 폴더
    archive_base: Path = field(default_factory=lambda: Path.home() / "_OrganizedFiles")

    # 중복 파일 아카이브 폴더
    duplicates_archive: Path = field(default=None)

    # 정리된 파일 저장 폴더
    organized_archive: Path = field(default=None)

    # 드라이 런 모드 (실제 파일 이동 없이 미리보기)
    dry_run: bool = True

    # 휴지통 사용 여부 (False면 아카이브 폴더로 이동)
    use_recycle_bin: bool = False

    # 분석할 텍스트 파일 확장자
    text_extensions: Set[str] = field(default_factory=lambda: {
        '.txt', '.md', '.py', '.js', '.java', '.c', '.cpp', '.h',
        '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.ini',
        '.cfg', '.conf', '.log', '.csv', '.rst', '.tex'
    })

    # 문서 파일 확장자
    document_extensions: Set[str] = field(default_factory=lambda: {
        '.doc', '.docx', '.pdf', '.ppt', '.pptx', '.xls', '.xlsx',
        '.odt', '.ods', '.odp', '.rtf'
    })

    # 이미지 파일 확장자
    image_extensions: Set[str] = field(default_factory=lambda: {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp',
        '.ico', '.tiff', '.raw'
    })

    # 제외할 폴더 이름들
    excluded_dirs: Set[str] = field(default_factory=lambda: {
        '.git', '.svn', '__pycache__', 'node_modules', '.venv',
        'venv', '.idea', '.vscode', '_OrganizedFiles', '$RECYCLE.BIN',
        'System Volume Information'
    })

    # 제외할 파일 패턴들
    excluded_patterns: Set[str] = field(default_factory=lambda: {
        '*.tmp', '*.temp', '~*', 'desktop.ini', 'Thumbs.db', '.DS_Store'
    })

    # 최소 파일 크기 (바이트) - 이보다 작은 파일은 중복 검사에서 제외
    min_file_size: int = 1

    # 파일명 유사도 임계값 (0.0 ~ 1.0)
    filename_similarity_threshold: float = 0.6

    # 내용 유사도 임계값 (0 ~ 100, ssdeep 퍼지 해싱용)
    content_similarity_threshold: int = 75

    # 로그 파일 경로
    log_file: Path = field(default=None)

    # LLM 분류 설정
    llm_max_file_size: int = 5 * 1024 * 1024  # 5MB
    llm_content_preview_length: int = 2000  # 2000자
    llm_batch_size_limit: int = 50  # LLM 자동 분류 최대 파일 수

    def __post_init__(self):
        """초기화 후 처리"""
        if self.duplicates_archive is None:
            self.duplicates_archive = self.archive_base / "Duplicates"
        if self.organized_archive is None:
            self.organized_archive = self.archive_base / "Organized"
        if self.log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = self.archive_base / "logs" / f"organizer_{timestamp}.log"


# 주제 분류를 위한 기본 카테고리 키워드
DEFAULT_CATEGORIES = {
    "업무_문서": ["보고서", "회의", "기획", "제안서", "계약", "invoice", "report", "meeting", "proposal"],
    "개발_프로젝트": ["python", "java", "javascript", "code", "프로그램", "개발", "소스", "function", "class", "def"],
    "재무_회계": ["세금", "급여", "예산", "결산", "영수증", "tax", "budget", "salary", "receipt", "invoice"],
    "개인_문서": ["이력서", "자기소개", "resume", "cv", "personal"],
    "교육_학습": ["강의", "교육", "학습", "course", "tutorial", "lesson", "study"],
    "미디어": ["사진", "영상", "음악", "photo", "video", "music", "image"],
}


# 파일 유형별 기본 분류 폴더
FILE_TYPE_FOLDERS = {
    "documents": ["문서"],
    "images": ["이미지"],
    "videos": ["영상"],
    "audio": ["오디오"],
    "archives": ["압축파일"],
    "code": ["코드"],
    "data": ["데이터"],
    "others": ["기타"],
}
