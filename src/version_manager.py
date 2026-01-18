"""
파일 버전 관리 모듈: 파일명 유사성 및 메타데이터 기반 버전 그룹화
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from difflib import SequenceMatcher
from datetime import datetime

from .config import OrganizerConfig
from .duplicate_finder import FileInfo

try:
    import ssdeep
    SSDEEP_AVAILABLE = True
except ImportError:
    SSDEEP_AVAILABLE = False


@dataclass
class VersionGroup:
    """동일 문서의 버전 그룹"""
    base_name: str  # 기준 파일명 (버전 정보 제거)
    files: List[FileInfo] = field(default_factory=list)
    extension: str = ""

    def add_file(self, file_info: FileInfo):
        """파일 추가"""
        self.files.append(file_info)
        if not self.extension and file_info.path.suffix:
            self.extension = file_info.path.suffix

    def sort_by_date(self, newest_first: bool = True):
        """수정일 기준 정렬"""
        self.files.sort(key=lambda f: f.modified_time, reverse=newest_first)

    def get_latest(self) -> Optional[FileInfo]:
        """가장 최신 파일 반환"""
        if not self.files:
            return None
        self.sort_by_date(newest_first=True)
        return self.files[0]

    def get_oldest(self) -> Optional[FileInfo]:
        """가장 오래된 파일 반환"""
        if not self.files:
            return None
        self.sort_by_date(newest_first=False)
        return self.files[0]

    @property
    def count(self) -> int:
        """파일 수"""
        return len(self.files)


class VersionManager:
    """파일 버전 관리 클래스"""

    # 버전 패턴 정규식
    VERSION_PATTERNS = [
        # 숫자 버전: _v1, _v2, -v1, (1), [1]
        r'[_\-\s]?v(\d+)',
        r'\((\d+)\)',
        r'\[(\d+)\]',
        # 날짜 버전: _20231215, _2023-12-15
        r'[_\-](\d{8})',
        r'[_\-](\d{4}[-_]\d{2}[-_]\d{2})',
        # 한글 버전 표시
        r'[_\-\s]?(최종|final|수정|수정본|완료|완성)',
        r'[_\-\s]?(초안|draft|임시|temp)',
        r'[_\-\s]?(백업|backup|bak)',
        r'[_\-\s]?(복사본|copy|사본)',
        # 영문 버전 표시
        r'[_\-\s]?(old|new|latest|original)',
        r'[_\-\s]?(rev\d*|revision\d*)',
    ]

    # 컴파일된 패턴
    COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in VERSION_PATTERNS]

    def __init__(self, config: OrganizerConfig):
        self.config = config
        self._fuzzy_hash_cache: Dict[Path, str] = {}

    def _extract_base_name(self, filename: str) -> str:
        """
        파일명에서 버전 정보를 제거하고 기본 이름 추출

        Args:
            filename: 확장자 제외 파일명

        Returns:
            버전 정보가 제거된 기본 파일명
        """
        base_name = filename

        # 모든 버전 패턴 제거
        for pattern in self.COMPILED_PATTERNS:
            base_name = pattern.sub('', base_name)

        # 연속된 구분자 정리
        base_name = re.sub(r'[_\-\s]+', '_', base_name)
        base_name = base_name.strip('_- ')

        return base_name if base_name else filename

    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """
        두 파일명의 유사도 계산 (0.0 ~ 1.0)

        Args:
            name1: 첫 번째 파일명
            name2: 두 번째 파일명

        Returns:
            유사도 점수
        """
        # 기본 이름 추출
        base1 = self._extract_base_name(name1).lower()
        base2 = self._extract_base_name(name2).lower()

        # SequenceMatcher로 유사도 계산
        return SequenceMatcher(None, base1, base2).ratio()

    def _has_version_indicator(self, filename: str) -> bool:
        """파일명에 버전 표시가 있는지 확인"""
        for pattern in self.COMPILED_PATTERNS:
            if pattern.search(filename):
                return True
        return False

    def _extract_version_info(self, filename: str) -> Dict:
        """
        파일명에서 버전 정보 추출

        Args:
            filename: 파일명

        Returns:
            버전 정보 딕셔너리
        """
        info = {
            'numeric_version': None,
            'date_version': None,
            'status': None,  # final, draft, backup 등
            'is_copy': False,
        }

        # 숫자 버전
        numeric_match = re.search(r'[_\-\s]?v(\d+)', filename, re.IGNORECASE)
        if numeric_match:
            info['numeric_version'] = int(numeric_match.group(1))

        # 괄호 안 숫자
        paren_match = re.search(r'\((\d+)\)', filename)
        if paren_match and info['numeric_version'] is None:
            info['numeric_version'] = int(paren_match.group(1))

        # 날짜 버전
        date_match = re.search(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})', filename)
        if date_match:
            try:
                year, month, day = map(int, date_match.groups())
                if 1990 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    info['date_version'] = f"{year}-{month:02d}-{day:02d}"
            except ValueError:
                pass

        # 상태 표시
        if re.search(r'(최종|final|완료|완성)', filename, re.IGNORECASE):
            info['status'] = 'final'
        elif re.search(r'(초안|draft|임시|temp)', filename, re.IGNORECASE):
            info['status'] = 'draft'
        elif re.search(r'(백업|backup|bak)', filename, re.IGNORECASE):
            info['status'] = 'backup'

        # 복사본 여부
        if re.search(r'(복사본|copy|사본|\(\d+\))', filename, re.IGNORECASE):
            info['is_copy'] = True

        return info

    def _calculate_fuzzy_hash(self, file_path: Path) -> Optional[str]:
        """
        파일의 ssdeep 퍼지 해시 계산

        Args:
            file_path: 파일 경로

        Returns:
            ssdeep 해시 문자열 또는 None (오류 시)
        """
        if not SSDEEP_AVAILABLE:
            return None

        # 캐시 확인
        if file_path in self._fuzzy_hash_cache:
            return self._fuzzy_hash_cache[file_path]

        try:
            fuzzy_hash = ssdeep.hash_from_file(str(file_path))
            self._fuzzy_hash_cache[file_path] = fuzzy_hash
            return fuzzy_hash
        except (IOError, OSError, PermissionError):
            return None

    def _calculate_fuzzy_similarity(self, hash1: str, hash2: str) -> int:
        """
        두 ssdeep 해시 간 유사도 계산

        Args:
            hash1: 첫 번째 ssdeep 해시
            hash2: 두 번째 ssdeep 해시

        Returns:
            유사도 점수 (0-100)
        """
        if not SSDEEP_AVAILABLE or not hash1 or not hash2:
            return 0

        try:
            return ssdeep.compare(hash1, hash2)
        except Exception:
            return 0

    def find_version_groups(self, files: List[FileInfo]) -> List[VersionGroup]:
        """
        파일 목록에서 버전 그룹 탐지 (파일명 유사도 + 내용 유사도 기반)

        Args:
            files: FileInfo 리스트

        Returns:
            VersionGroup 리스트
        """
        # 확장자별로 그룹화
        by_extension: Dict[str, List[FileInfo]] = defaultdict(list)
        for file_info in files:
            ext = file_info.path.suffix.lower()
            by_extension[ext].append(file_info)

        all_groups: List[VersionGroup] = []

        for ext, ext_files in by_extension.items():
            # 1단계: 파일명 유사도 기반 그룹화
            base_name_groups: Dict[str, List[FileInfo]] = defaultdict(list)

            for file_info in ext_files:
                stem = file_info.path.stem
                base_name = self._extract_base_name(stem)
                base_name_groups[base_name.lower()].append(file_info)

            # 2개 이상 파일이 있는 그룹만 선택
            for base_name, group_files in base_name_groups.items():
                if len(group_files) > 1:
                    group = VersionGroup(base_name=base_name, extension=ext)
                    for f in group_files:
                        group.add_file(f)
                    group.sort_by_date(newest_first=True)
                    all_groups.append(group)

            # 2단계: 내용 유사도 기반 그룹화 (ssdeep 사용)
            if SSDEEP_AVAILABLE:
                content_groups = self._find_content_similar_groups(ext_files)
                all_groups.extend(content_groups)

        # 추가: 유사도 기반 그룹 병합 시도
        all_groups = self._merge_similar_groups(all_groups)

        return all_groups

    def _find_content_similar_groups(self, files: List[FileInfo]) -> List[VersionGroup]:
        """
        내용 유사도 기반 버전 그룹 탐지 (ssdeep 퍼지 해싱)

        Args:
            files: 같은 확장자의 파일 목록

        Returns:
            내용이 유사한 파일들의 버전 그룹 리스트
        """
        if not SSDEEP_AVAILABLE or len(files) < 2:
            return []

        # 퍼지 해시 계산
        file_hashes: List[Tuple[FileInfo, str]] = []
        for file_info in files:
            fuzzy_hash = self._calculate_fuzzy_hash(file_info.path)
            if fuzzy_hash:
                file_hashes.append((file_info, fuzzy_hash))

        if len(file_hashes) < 2:
            return []

        # 내용 유사도 기반 그룹화
        content_groups: List[VersionGroup] = []
        used_indices = set()

        # 유사도 임계값 (설정 가능, 기본 75% 유사도)
        similarity_threshold = getattr(
            self.config,
            'content_similarity_threshold',
            75
        )

        for i, (file1, hash1) in enumerate(file_hashes):
            if i in used_indices:
                continue

            # 새 그룹 생성
            similar_files = [file1]
            used_indices.add(i)

            # 다른 파일들과 비교
            for j, (file2, hash2) in enumerate(file_hashes):
                if j <= i or j in used_indices:
                    continue

                similarity = self._calculate_fuzzy_similarity(hash1, hash2)

                # 유사도가 임계값 이상이면 같은 그룹
                if similarity >= similarity_threshold:
                    similar_files.append(file2)
                    used_indices.add(j)

            # 2개 이상 유사 파일이 있으면 버전 그룹 생성
            if len(similar_files) > 1:
                # 기본 이름은 가장 최신 파일의 이름 사용
                latest_file = max(similar_files, key=lambda f: f.modified_time)
                base_name = self._extract_base_name(latest_file.path.stem)

                group = VersionGroup(
                    base_name=f"{base_name}_content_similar",
                    extension=latest_file.path.suffix.lower()
                )

                for f in similar_files:
                    group.add_file(f)

                group.sort_by_date(newest_first=True)
                content_groups.append(group)

        return content_groups

    def _merge_similar_groups(self, groups: List[VersionGroup]) -> List[VersionGroup]:
        """
        유사한 기본 이름을 가진 그룹 병합

        Args:
            groups: 버전 그룹 리스트

        Returns:
            병합된 그룹 리스트
        """
        if len(groups) <= 1:
            return groups

        merged = []
        used = set()

        for i, group1 in enumerate(groups):
            if i in used:
                continue

            current_group = VersionGroup(
                base_name=group1.base_name,
                extension=group1.extension
            )
            for f in group1.files:
                current_group.add_file(f)
            used.add(i)

            # 같은 확장자의 다른 그룹과 유사도 비교
            for j, group2 in enumerate(groups):
                if j in used or j <= i:
                    continue
                if group1.extension != group2.extension:
                    continue

                similarity = self._calculate_similarity(
                    group1.base_name, group2.base_name
                )

                if similarity >= self.config.filename_similarity_threshold:
                    for f in group2.files:
                        current_group.add_file(f)
                    used.add(j)

            if current_group.count > 1:
                current_group.sort_by_date(newest_first=True)
                merged.append(current_group)

        return merged

    def analyze_version_group(self, group: VersionGroup) -> Dict:
        """
        버전 그룹 분석 결과 반환

        Args:
            group: 분석할 버전 그룹

        Returns:
            분석 결과 딕셔너리
        """
        group.sort_by_date(newest_first=True)

        analysis = {
            'base_name': group.base_name,
            'extension': group.extension,
            'total_files': group.count,
            'files': [],
            'recommended_keep': None,
            'recommended_archive': [],
        }

        final_version = None
        latest_version = group.files[0] if group.files else None

        for file_info in group.files:
            version_info = self._extract_version_info(file_info.path.stem)
            modified_date = datetime.fromtimestamp(file_info.modified_time)

            file_analysis = {
                'path': str(file_info.path),
                'filename': file_info.path.name,
                'size': file_info.size,
                'modified': modified_date.strftime('%Y-%m-%d %H:%M:%S'),
                'version_info': version_info,
            }
            analysis['files'].append(file_analysis)

            # 'final' 상태 파일 찾기
            if version_info['status'] == 'final':
                final_version = file_info

        # 보존 추천: final 버전이 있으면 그것, 아니면 최신 파일
        if final_version:
            analysis['recommended_keep'] = str(final_version.path)
        elif latest_version:
            analysis['recommended_keep'] = str(latest_version.path)

        # 나머지는 아카이브 추천
        for file_info in group.files:
            if str(file_info.path) != analysis['recommended_keep']:
                analysis['recommended_archive'].append(str(file_info.path))

        return analysis

    def suggest_consolidation(self, groups: List[VersionGroup]) -> List[Dict]:
        """
        버전 그룹들에 대한 통합 제안

        Args:
            groups: 버전 그룹 리스트

        Returns:
            통합 제안 리스트
        """
        suggestions = []

        for group in groups:
            analysis = self.analyze_version_group(group)

            suggestion = {
                'group_info': {
                    'base_name': analysis['base_name'],
                    'extension': analysis['extension'],
                    'file_count': analysis['total_files'],
                },
                'keep': {
                    'path': analysis['recommended_keep'],
                    'reason': '가장 최신 버전 또는 최종본으로 표시된 파일'
                },
                'archive': [
                    {
                        'path': path,
                        'reason': '이전 버전 또는 복사본'
                    }
                    for path in analysis['recommended_archive']
                ],
                'files_detail': analysis['files'],
            }

            suggestions.append(suggestion)

        return suggestions


def format_version_report(groups: List[VersionGroup], manager: VersionManager) -> str:
    """
    버전 그룹 보고서 포맷팅

    Args:
        groups: 버전 그룹 리스트
        manager: VersionManager 인스턴스

    Returns:
        포맷된 보고서 문자열
    """
    lines = []
    lines.append("=" * 60)
    lines.append("📋 파일 버전 분석 보고서")
    lines.append("=" * 60)
    lines.append(f"\n총 {len(groups)}개의 버전 그룹 발견\n")

    for i, group in enumerate(groups, 1):
        analysis = manager.analyze_version_group(group)

        lines.append(f"\n{'─' * 50}")
        lines.append(f"그룹 {i}: {analysis['base_name']}{analysis['extension']}")
        lines.append(f"파일 수: {analysis['total_files']}개")
        lines.append("")

        for j, file_detail in enumerate(analysis['files'], 1):
            is_keep = file_detail['path'] == analysis['recommended_keep']
            marker = "✓ [보존 추천]" if is_keep else "  [아카이브 추천]"

            lines.append(f"  {j}. {file_detail['filename']}")
            lines.append(f"     {marker}")
            lines.append(f"     수정일: {file_detail['modified']}")
            lines.append(f"     크기: {file_detail['size']:,} bytes")

            if file_detail['version_info']['status']:
                lines.append(f"     상태: {file_detail['version_info']['status']}")
            lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)
