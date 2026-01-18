"""
논문 PDF 정리 모듈

학술 논문 PDF의 메타데이터를 추출하고, 주제별/저자별로 분류하며
논문 제목으로 파일명을 변경하는 기능 제공
"""

import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


@dataclass
class PaperMetadata:
    """논문 메타데이터"""
    file_path: Path
    title: Optional[str] = None
    authors: List[str] = None
    year: Optional[int] = None
    keywords: List[str] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None

    # 추출된 정보
    first_author: Optional[str] = None
    topic: Optional[str] = None  # 주제 (키워드 기반)

    def __post_init__(self):
        if self.authors is None:
            self.authors = []
        if self.keywords is None:
            self.keywords = []
        if self.authors and not self.first_author:
            self.first_author = self.authors[0]


class PaperOrganizer:
    """논문 PDF 정리 클래스"""

    def __init__(self):
        if not PDF_AVAILABLE:
            print("⚠️ PyPDF2가 설치되지 않았습니다. PDF 기능이 제한됩니다.")
            print("   설치: pip install PyPDF2")

    def extract_metadata(self, pdf_path: Path) -> Optional[PaperMetadata]:
        """
        PDF에서 메타데이터 추출

        Args:
            pdf_path: PDF 파일 경로

        Returns:
            PaperMetadata 또는 None
        """
        if not PDF_AVAILABLE:
            return None

        if not pdf_path.exists() or pdf_path.suffix.lower() != '.pdf':
            return None

        try:
            reader = PdfReader(str(pdf_path))
            metadata = reader.metadata

            if not metadata:
                # 메타데이터 없으면 텍스트에서 추출 시도
                return self._extract_from_text(pdf_path, reader)

            # 메타데이터에서 정보 추출
            title = metadata.get('/Title', '').strip()
            author_str = metadata.get('/Author', '').strip()
            subject = metadata.get('/Subject', '').strip()
            keywords_str = metadata.get('/Keywords', '').strip()

            # 저자 파싱
            authors = self._parse_authors(author_str)

            # 키워드 파싱
            keywords = self._parse_keywords(keywords_str)
            if subject:
                keywords.append(subject)

            # 연도 추출 (제목, 파일명, 생성일에서)
            year = self._extract_year(title, pdf_path.name)
            if not year and metadata.get('/CreationDate'):
                year = self._parse_pdf_date(metadata['/CreationDate'])

            # 제목이 없으면 텍스트에서 추출
            if not title:
                text_metadata = self._extract_from_text(pdf_path, reader)
                if text_metadata and text_metadata.title:
                    title = text_metadata.title

            paper_meta = PaperMetadata(
                file_path=pdf_path,
                title=title if title else None,
                authors=authors,
                year=year,
                keywords=keywords,
            )

            # 주제 추론 (키워드 기반)
            paper_meta.topic = self._infer_topic(keywords, title)

            return paper_meta

        except Exception as e:
            print(f"⚠️ PDF 메타데이터 추출 실패 ({pdf_path.name}): {e}")
            return None

    def _extract_from_text(self, pdf_path: Path, reader: 'PdfReader') -> Optional[PaperMetadata]:
        """
        PDF 텍스트에서 메타데이터 추출 (메타데이터가 없을 때)

        첫 페이지에서 제목, 저자 등을 추출
        """
        try:
            # 첫 페이지 텍스트
            if len(reader.pages) == 0:
                return None

            first_page_text = reader.pages[0].extract_text()

            # 제목 추출 (보통 가장 큰 텍스트 또는 첫 줄)
            lines = [l.strip() for l in first_page_text.split('\n') if l.strip()]

            title = None
            authors = []
            year = None

            # 제목은 보통 처음 1-3줄 내에 있음
            for i, line in enumerate(lines[:5]):
                # 너무 긴 줄은 제목이 아닐 가능성
                if len(line) > 200:
                    continue
                # Abstract, Introduction 등이 나오면 그 전까지가 메타데이터
                if any(keyword in line.lower() for keyword in ['abstract', 'introduction', '초록']):
                    break
                # 대문자가 많거나 특정 패턴이면 제목
                if i == 0 or (line.isupper() or len(line) > 20):
                    title = line
                    break

            # 저자 추출 (이메일, 대학명 등으로 패턴 인식)
            author_pattern = r'([A-Z][a-z]+ [A-Z][a-z]+(?:, [A-Z][a-z]+ [A-Z][a-z]+)*)'
            author_matches = re.findall(author_pattern, first_page_text[:1000])
            if author_matches:
                authors = [m.strip() for m in author_matches[:5]]  # 최대 5명

            # 연도 추출
            year = self._extract_year(first_page_text, pdf_path.name)

            return PaperMetadata(
                file_path=pdf_path,
                title=title,
                authors=authors,
                year=year,
            )

        except Exception as e:
            print(f"⚠️ PDF 텍스트 추출 실패: {e}")
            return None

    def _parse_authors(self, author_str: str) -> List[str]:
        """저자 문자열 파싱"""
        if not author_str:
            return []

        # 여러 구분자로 분리 시도
        separators = [';', ',', ' and ', ' AND ', '&']
        authors = [author_str]

        for sep in separators:
            if sep in author_str:
                authors = [a.strip() for a in author_str.split(sep)]
                break

        # 빈 문자열 제거
        authors = [a for a in authors if a]

        return authors[:10]  # 최대 10명

    def _parse_keywords(self, keywords_str: str) -> List[str]:
        """키워드 문자열 파싱"""
        if not keywords_str:
            return []

        # 구분자로 분리
        separators = [';', ',', '|']
        keywords = [keywords_str]

        for sep in separators:
            if sep in keywords_str:
                keywords = [k.strip() for k in keywords_str.split(sep)]
                break

        return [k for k in keywords if k]

    def _extract_year(self, *texts: str) -> Optional[int]:
        """텍스트에서 연도 추출"""
        for text in texts:
            if not text:
                continue
            # 4자리 연도 패턴 (1900-2099)
            matches = re.findall(r'\b(19\d{2}|20\d{2})\b', text)
            if matches:
                # 가장 최근 연도 반환
                years = [int(y) for y in matches]
                current_year = datetime.now().year
                valid_years = [y for y in years if 1900 <= y <= current_year + 1]
                if valid_years:
                    return max(valid_years)
        return None

    def _parse_pdf_date(self, date_str: str) -> Optional[int]:
        """PDF 날짜 형식 파싱 (D:20210101...)"""
        try:
            # D:YYYYMMDDHHmmSS 형식
            match = re.match(r'D:(\d{4})', date_str)
            if match:
                return int(match.group(1))
        except:
            pass
        return None

    def _infer_topic(self, keywords: List[str], title: Optional[str]) -> Optional[str]:
        """
        키워드와 제목에서 주제 추론

        Returns:
            추론된 주제 (예: "Machine Learning", "Quantum Computing")
        """
        # 주요 주제 패턴 정의
        topic_patterns = {
            "Machine Learning": ['machine learning', 'deep learning', 'neural network', 'ai', 'artificial intelligence'],
            "Computer Vision": ['computer vision', 'image recognition', 'object detection', 'cv'],
            "Natural Language Processing": ['nlp', 'natural language', 'text processing', 'language model'],
            "Quantum Computing": ['quantum', 'qubit', 'quantum computing'],
            "Database": ['database', 'sql', 'nosql', 'data management'],
            "Security": ['security', 'cryptography', 'encryption', 'vulnerability'],
            "Networks": ['network', 'protocol', 'tcp', 'routing'],
            "Software Engineering": ['software engineering', 'programming', 'development'],
            "Algorithms": ['algorithm', 'optimization', 'complexity'],
        }

        # 키워드와 제목을 합쳐서 검사
        text = ' '.join(keywords).lower()
        if title:
            text += ' ' + title.lower()

        # 매칭되는 주제 찾기
        for topic, patterns in topic_patterns.items():
            if any(pattern in text for pattern in patterns):
                return topic

        # 매칭 안 되면 첫 키워드 반환
        if keywords:
            return keywords[0].title()

        return "General"

    def generate_paper_filename(self, metadata: PaperMetadata) -> str:
        """
        논문 메타데이터에서 파일명 생성

        Returns:
            새로운 파일명 (예: "Smith_2021_Deep_Learning.pdf")
        """
        parts = []

        # 첫 저자 성
        if metadata.first_author:
            # 성 추출 (보통 마지막 단어)
            name_parts = metadata.first_author.split()
            last_name = name_parts[-1] if name_parts else metadata.first_author
            # 특수문자 제거
            last_name = re.sub(r'[^\w]', '', last_name)
            parts.append(last_name)

        # 연도
        if metadata.year:
            parts.append(str(metadata.year))

        # 제목 (처음 5단어, 또는 50자까지)
        if metadata.title:
            title = metadata.title
            # 특수문자 제거 및 공백을 언더스코어로
            title = re.sub(r'[^\w\s]', '', title)
            title = re.sub(r'\s+', '_', title)
            # 길이 제한
            words = title.split('_')[:5]
            title_part = '_'.join(words)
            if len(title_part) > 50:
                title_part = title_part[:50]
            parts.append(title_part)

        # 조합
        if parts:
            filename = '_'.join(parts) + '.pdf'
        else:
            # 메타데이터 없으면 원본 유지
            filename = metadata.file_path.name

        return filename

    def classify_by_author(self, metadata: PaperMetadata) -> str:
        """저자별 분류 (첫 저자 성 기준)"""
        if metadata.first_author:
            name_parts = metadata.first_author.split()
            return name_parts[-1] if name_parts else "Unknown"
        return "Unknown"

    def classify_by_topic(self, metadata: PaperMetadata) -> str:
        """주제별 분류"""
        return metadata.topic if metadata.topic else "General"

    def classify_by_year(self, metadata: PaperMetadata) -> str:
        """연도별 분류"""
        return str(metadata.year) if metadata.year else "Unknown"
