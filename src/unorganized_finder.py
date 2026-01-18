"""
미분류 파일 찾기 및 재정리 모듈

폴더 구조 없이 루트에 있는 파일들을 찾아서 재정리
"""

from pathlib import Path
from typing import List, Set, Dict
from dataclasses import dataclass

from .duplicate_finder import FileInfo
from .config import OrganizerConfig


@dataclass
class UnorganizedFile:
    """미분류 파일 정보"""
    file_info: FileInfo
    is_root_level: bool  # True면 완전히 루트 (하위 폴더 없음)
    depth_from_root: int  # 루트로부터 깊이


class UnorganizedFinder:
    """미분류 파일 탐지 클래스"""

    def __init__(self, config: OrganizerConfig):
        self.config = config

    def find_unorganized_files(
        self,
        search_directory: Path,
        max_depth: int = 1,
        include_subfolders: bool = False
    ) -> List[UnorganizedFile]:
        """
        미분류 파일 찾기

        Args:
            search_directory: 검색할 디렉토리
            max_depth: 최대 깊이 (1이면 바로 아래 파일만)
            include_subfolders: 하위 폴더의 파일도 포함할지 여부

        Returns:
            미분류 파일 리스트
        """
        unorganized = []

        if not search_directory.exists():
            return unorganized

        # 루트 레벨 파일 찾기
        for item in search_directory.iterdir():
            if item.is_file():
                # 제외 패턴 체크
                if self._should_exclude(item):
                    continue

                file_info = FileInfo(path=item, size=0)
                unorganized.append(UnorganizedFile(
                    file_info=file_info,
                    is_root_level=True,
                    depth_from_root=0
                ))

        # 하위 폴더 포함 시
        if include_subfolders and max_depth > 1:
            for item in search_directory.iterdir():
                if item.is_dir() and not self._should_exclude_dir(item):
                    sub_files = self._find_files_in_depth(
                        item,
                        current_depth=1,
                        max_depth=max_depth
                    )
                    unorganized.extend(sub_files)

        return unorganized

    def _find_files_in_depth(
        self,
        directory: Path,
        current_depth: int,
        max_depth: int
    ) -> List[UnorganizedFile]:
        """
        지정된 깊이까지 파일 찾기

        Args:
            directory: 현재 디렉토리
            current_depth: 현재 깊이
            max_depth: 최대 깊이

        Returns:
            파일 리스트
        """
        files = []

        if current_depth > max_depth:
            return files

        try:
            for item in directory.iterdir():
                if item.is_file():
                    if not self._should_exclude(item):
                        file_info = FileInfo(path=item, size=0)
                        files.append(UnorganizedFile(
                            file_info=file_info,
                            is_root_level=False,
                            depth_from_root=current_depth
                        ))
                elif item.is_dir() and not self._should_exclude_dir(item):
                    # 재귀적으로 탐색
                    sub_files = self._find_files_in_depth(
                        item,
                        current_depth + 1,
                        max_depth
                    )
                    files.extend(sub_files)
        except (PermissionError, OSError):
            pass

        return files

    def _should_exclude(self, file_path: Path) -> bool:
        """파일 제외 여부 확인"""
        import fnmatch

        # 파일 패턴 체크
        for pattern in self.config.excluded_patterns:
            if fnmatch.fnmatch(file_path.name, pattern):
                return True

        return False

    def _should_exclude_dir(self, dir_path: Path) -> bool:
        """폴더 제외 여부 확인"""
        return dir_path.name in self.config.excluded_dirs

    def find_existing_categories(
        self,
        organized_dir: Path
    ) -> Dict[str, Path]:
        """
        이미 존재하는 카테고리 폴더 찾기

        Args:
            organized_dir: 정리된 파일들이 있는 디렉토리

        Returns:
            {카테고리명: 경로} 딕셔너리
        """
        categories = {}

        if not organized_dir.exists():
            return categories

        try:
            for item in organized_dir.iterdir():
                if item.is_dir():
                    categories[item.name] = item
        except (PermissionError, OSError):
            pass

        return categories

    def suggest_category_for_file(
        self,
        file_path: Path,
        existing_categories: Dict[str, Path]
    ) -> str:
        """
        파일에 적합한 기존 카테고리 제안

        Args:
            file_path: 파일 경로
            existing_categories: 기존 카테고리 딕셔너리

        Returns:
            추천 카테고리명
        """
        # 확장자 기반 매칭
        ext = file_path.suffix.lower()

        # 문서
        if ext in self.config.document_extensions:
            for cat in ['문서', '업무', '업무_문서', 'Documents']:
                if cat in existing_categories:
                    return cat

        # 이미지
        if ext in self.config.image_extensions:
            for cat in ['이미지', '사진', '미디어', 'Images', 'Photos']:
                if cat in existing_categories:
                    return cat

        # 기타 확장자별
        video_exts = {'.mp4', '.avi', '.mkv', '.mov'}
        audio_exts = {'.mp3', '.wav', '.flac'}
        archive_exts = {'.zip', '.rar', '.7z', '.tar', '.gz'}

        if ext in video_exts:
            for cat in ['영상', '비디오', 'Videos']:
                if cat in existing_categories:
                    return cat

        if ext in audio_exts:
            for cat in ['음악', '오디오', 'Music', 'Audio']:
                if cat in existing_categories:
                    return cat

        if ext in archive_exts:
            for cat in ['압축파일', 'Archives']:
                if cat in existing_categories:
                    return cat

        # 매칭 안 되면 기타
        for cat in ['기타', 'Others', 'Misc']:
            if cat in existing_categories:
                return cat

        # 아무것도 없으면 새 카테고리
        return "미분류"

    def get_summary(self, unorganized_files: List[UnorganizedFile]) -> Dict:
        """
        미분류 파일 요약 정보

        Args:
            unorganized_files: 미분류 파일 리스트

        Returns:
            요약 딕셔너리
        """
        summary = {
            "total_files": len(unorganized_files),
            "root_level_files": sum(1 for f in unorganized_files if f.is_root_level),
            "nested_files": sum(1 for f in unorganized_files if not f.is_root_level),
            "by_extension": {},
            "total_size": 0,
        }

        for unorg in unorganized_files:
            ext = unorg.file_info.path.suffix.lower() or '.none'
            summary["by_extension"][ext] = summary["by_extension"].get(ext, 0) + 1
            summary["total_size"] += unorg.file_info.size

        return summary
