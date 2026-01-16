"""
지능형 파일 분류 모듈: 주제 및 날짜 기반 파일 분류
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from datetime import datetime
import string

from .config import OrganizerConfig, DEFAULT_CATEGORIES
from .duplicate_finder import FileInfo


@dataclass
class ClassificationResult:
    """분류 결과"""
    file_info: FileInfo
    category: str
    subcategory: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    confidence: float = 0.0
    keywords: List[str] = field(default_factory=list)
    target_path: Optional[Path] = None


class TextAnalyzer:
    """텍스트 분석 클래스"""

    # 한글 불용어
    KOREAN_STOPWORDS = {
        '이', '가', '을', '를', '의', '에', '에서', '으로', '로', '와', '과',
        '는', '은', '도', '만', '까지', '부터', '보다', '처럼', '같이',
        '그', '저', '이것', '그것', '저것', '여기', '거기', '저기',
        '하다', '되다', '있다', '없다', '않다', '이다', '아니다',
        '수', '것', '등', '및', '또는', '그리고', '하지만', '그러나',
    }

    # 영어 불용어
    ENGLISH_STOPWORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as',
        'into', 'through', 'during', 'before', 'after', 'above', 'below',
        'and', 'but', 'or', 'nor', 'so', 'yet', 'both', 'either', 'neither',
        'not', 'only', 'own', 'same', 'than', 'too', 'very', 'just',
        'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them',
    }

    def __init__(self):
        self.stopwords = self.KOREAN_STOPWORDS | self.ENGLISH_STOPWORDS

    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[Tuple[str, int]]:
        """
        텍스트에서 키워드 추출

        Args:
            text: 분석할 텍스트
            max_keywords: 최대 키워드 수

        Returns:
            (키워드, 빈도) 튜플 리스트
        """
        # 텍스트 정규화
        text = text.lower()

        # 특수문자 제거 (한글, 영문, 숫자만 유지)
        text = re.sub(r'[^\w\s가-힣]', ' ', text)

        # 토큰화
        tokens = text.split()

        # 불용어 및 짧은 단어 제거
        tokens = [
            t for t in tokens
            if t not in self.stopwords
            and len(t) > 1
            and not t.isdigit()
        ]

        # 빈도 계산
        counter = Counter(tokens)

        return counter.most_common(max_keywords)

    def calculate_category_score(self, text: str, category_keywords: List[str]) -> float:
        """
        텍스트와 카테고리 키워드 간의 매칭 점수 계산

        Args:
            text: 분석할 텍스트
            category_keywords: 카테고리 키워드 리스트

        Returns:
            매칭 점수 (0.0 ~ 1.0)
        """
        text_lower = text.lower()
        matches = sum(1 for kw in category_keywords if kw.lower() in text_lower)

        if not category_keywords:
            return 0.0

        return matches / len(category_keywords)


class FileClassifier:
    """파일 분류 클래스"""

    def __init__(self, config: OrganizerConfig):
        self.config = config
        self.text_analyzer = TextAnalyzer()
        self.categories = DEFAULT_CATEGORIES.copy()

    def add_category(self, name: str, keywords: List[str]):
        """사용자 정의 카테고리 추가"""
        self.categories[name] = keywords

    def _read_text_file(self, file_path: Path, max_bytes: int = 50000) -> Optional[str]:
        """
        텍스트 파일 내용 읽기

        Args:
            file_path: 파일 경로
            max_bytes: 최대 읽기 바이트 수

        Returns:
            파일 내용 또는 None
        """
        try:
            # 다양한 인코딩 시도
            encodings = ['utf-8', 'cp949', 'euc-kr', 'latin-1']

            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read(max_bytes)
                except UnicodeDecodeError:
                    continue

            return None
        except (IOError, OSError, PermissionError):
            return None

    def _get_file_type(self, file_path: Path) -> str:
        """
        파일 유형 분류

        Args:
            file_path: 파일 경로

        Returns:
            파일 유형 문자열
        """
        ext = file_path.suffix.lower()

        if ext in self.config.text_extensions:
            return "text"
        elif ext in self.config.document_extensions:
            return "document"
        elif ext in self.config.image_extensions:
            return "image"
        elif ext in {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}:
            return "video"
        elif ext in {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'}:
            return "audio"
        elif ext in {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'}:
            return "archive"
        elif ext in {'.exe', '.msi', '.dmg', '.deb', '.rpm'}:
            return "executable"
        else:
            return "other"

    def classify_by_content(self, file_info: FileInfo) -> ClassificationResult:
        """
        파일 내용 기반 분류

        Args:
            file_info: 파일 정보

        Returns:
            분류 결과
        """
        result = ClassificationResult(file_info=file_info, category="기타")

        file_type = self._get_file_type(file_info.path)

        # 텍스트 파일인 경우 내용 분석
        if file_type == "text":
            content = self._read_text_file(file_info.path)
            if content:
                # 키워드 추출
                keywords = self.text_analyzer.extract_keywords(content)
                result.keywords = [kw for kw, _ in keywords]

                # 카테고리 매칭
                best_category = None
                best_score = 0.0

                # 파일 내용과 파일명 결합하여 분석
                analysis_text = content + " " + file_info.path.stem

                for category, cat_keywords in self.categories.items():
                    score = self.text_analyzer.calculate_category_score(
                        analysis_text, cat_keywords
                    )
                    if score > best_score:
                        best_score = score
                        best_category = category

                if best_category and best_score > 0.1:
                    result.category = best_category
                    result.confidence = best_score
        else:
            # 비텍스트 파일: 파일명과 확장자 기반 분류
            result.category = self._classify_by_type(file_type)
            result.confidence = 0.8

        # 날짜 정보 추출
        result.year, result.month = self._extract_date_info(file_info)

        return result

    def _classify_by_type(self, file_type: str) -> str:
        """파일 유형 기반 기본 카테고리 반환"""
        type_to_category = {
            "text": "문서",
            "document": "문서",
            "image": "미디어",
            "video": "미디어",
            "audio": "미디어",
            "archive": "압축파일",
            "executable": "프로그램",
            "other": "기타",
        }
        return type_to_category.get(file_type, "기타")

    def _extract_date_info(self, file_info: FileInfo) -> Tuple[Optional[int], Optional[int]]:
        """
        파일에서 날짜 정보 추출 (수정일 기준)

        Args:
            file_info: 파일 정보

        Returns:
            (year, month) 튜플
        """
        try:
            # 파일 수정일 기준
            modified_time = datetime.fromtimestamp(file_info.modified_time)
            return modified_time.year, modified_time.month
        except (OSError, ValueError):
            return None, None

    def classify_by_date(self, file_info: FileInfo) -> ClassificationResult:
        """
        날짜 기반 분류

        Args:
            file_info: 파일 정보

        Returns:
            분류 결과
        """
        year, month = self._extract_date_info(file_info)

        result = ClassificationResult(
            file_info=file_info,
            category=self._classify_by_type(self._get_file_type(file_info.path)),
            year=year,
            month=month,
            confidence=1.0 if year else 0.5
        )

        return result

    def classify_files(self, files: List[FileInfo],
                       by_content: bool = True,
                       by_date: bool = True) -> List[ClassificationResult]:
        """
        파일 목록 분류

        Args:
            files: FileInfo 리스트
            by_content: 내용 기반 분류 여부
            by_date: 날짜 기반 분류 여부

        Returns:
            분류 결과 리스트
        """
        results = []

        for i, file_info in enumerate(files):
            if by_content:
                result = self.classify_by_content(file_info)
            else:
                result = self.classify_by_date(file_info)

            # 날짜 정보 보강
            if by_date and (result.year is None or result.month is None):
                year, month = self._extract_date_info(file_info)
                result.year = year
                result.month = month

            results.append(result)

            # 진행 상황 출력
            if (i + 1) % 100 == 0:
                print(f"   분류 진행: {i + 1}/{len(files)}")

        return results

    def generate_target_path(self, result: ClassificationResult,
                             base_path: Path,
                             include_date: bool = True) -> Path:
        """
        분류 결과에 따른 대상 경로 생성

        Args:
            result: 분류 결과
            base_path: 기준 경로
            include_date: 날짜 폴더 포함 여부

        Returns:
            대상 경로
        """
        path_parts = [base_path, result.category]

        if include_date and result.year:
            path_parts.append(str(result.year))
            if result.month:
                path_parts.append(f"{result.month:02d}")

        target_dir = Path(*[str(p) for p in path_parts])
        target_path = target_dir / result.file_info.path.name

        result.target_path = target_path
        return target_path

    def get_classification_summary(self, results: List[ClassificationResult]) -> Dict:
        """
        분류 결과 요약

        Args:
            results: 분류 결과 리스트

        Returns:
            요약 딕셔너리
        """
        summary = {
            "total_files": len(results),
            "by_category": defaultdict(int),
            "by_year": defaultdict(int),
            "by_year_month": defaultdict(int),
            "low_confidence": [],
        }

        for result in results:
            summary["by_category"][result.category] += 1

            if result.year:
                summary["by_year"][result.year] += 1
                if result.month:
                    key = f"{result.year}-{result.month:02d}"
                    summary["by_year_month"][key] += 1

            if result.confidence < 0.3:
                summary["low_confidence"].append({
                    "file": str(result.file_info.path),
                    "assigned_category": result.category,
                    "confidence": result.confidence,
                })

        # defaultdict를 일반 dict로 변환
        summary["by_category"] = dict(summary["by_category"])
        summary["by_year"] = dict(summary["by_year"])
        summary["by_year_month"] = dict(summary["by_year_month"])

        return summary


def format_classification_report(summary: Dict) -> str:
    """
    분류 결과 보고서 포맷팅

    Args:
        summary: 분류 요약 딕셔너리

    Returns:
        포맷된 보고서 문자열
    """
    lines = []
    lines.append("=" * 60)
    lines.append("📊 파일 분류 분석 보고서")
    lines.append("=" * 60)
    lines.append(f"\n총 파일 수: {summary['total_files']:,}개\n")

    # 카테고리별 분포
    lines.append("📁 카테고리별 분포:")
    lines.append("-" * 40)
    for category, count in sorted(summary["by_category"].items(),
                                  key=lambda x: x[1], reverse=True):
        percentage = (count / summary["total_files"]) * 100
        bar = "█" * int(percentage / 5)
        lines.append(f"  {category:<15} {count:>6}개 ({percentage:>5.1f}%) {bar}")

    # 연도별 분포
    if summary["by_year"]:
        lines.append(f"\n📅 연도별 분포:")
        lines.append("-" * 40)
        for year, count in sorted(summary["by_year"].items(), reverse=True):
            percentage = (count / summary["total_files"]) * 100
            lines.append(f"  {year}년: {count:>6}개 ({percentage:>5.1f}%)")

    # 신뢰도 낮은 파일
    if summary["low_confidence"]:
        lines.append(f"\n⚠️  분류 신뢰도 낮은 파일 (상위 10개):")
        lines.append("-" * 40)
        for item in summary["low_confidence"][:10]:
            lines.append(f"  - {Path(item['file']).name}")
            lines.append(f"    분류: {item['assigned_category']} "
                        f"(신뢰도: {item['confidence']:.1%})")

    lines.append("\n" + "=" * 60)

    return "\n".join(lines)
