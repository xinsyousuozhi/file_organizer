"""
파일 정리 도구 - 핵심 모듈

제공 기능:
- OrganizerConfig: 설정 클래스
- FileOrganizer: 통합 정리 클래스
- DuplicateFinder: 중복 파일 탐지
- VersionManager: 버전 파일 그룹화
- FileClassifier: 파일 분류
- FileMover: 안전한 파일 이동
"""

from .config import OrganizerConfig
from .organizer import FileOrganizer
from .duplicate_finder import DuplicateFinder
from .version_manager import VersionManager
from .classifier import FileClassifier
from .file_mover import FileMover

__all__ = [
    'OrganizerConfig',
    'FileOrganizer',
    'DuplicateFinder',
    'VersionManager',
    'FileClassifier',
    'FileMover',
]
