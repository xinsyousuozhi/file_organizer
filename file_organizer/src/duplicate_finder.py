"""
중복 파일 식별 모듈: SHA256 해싱을 사용하여 파일 내용 기반 중복 파일 탐지
"""

import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch

from .config import OrganizerConfig


@dataclass
class FileInfo:
    """파일 정보를 담는 데이터 클래스"""
    path: Path
    size: int
    hash: Optional[str] = None
    modified_time: float = 0.0
    created_time: float = 0.0

    def __post_init__(self):
        """파일 메타데이터 초기화"""
        if self.path.exists():
            stat = self.path.stat()
            self.size = stat.st_size
            self.modified_time = stat.st_mtime
            self.created_time = stat.st_ctime


@dataclass
class DuplicateGroup:
    """중복 파일 그룹"""
    hash: str
    files: List[FileInfo] = field(default_factory=list)
    total_size: int = 0

    def add_file(self, file_info: FileInfo):
        """파일 추가"""
        self.files.append(file_info)
        self.total_size += file_info.size

    @property
    def wasted_space(self) -> int:
        """낭비되는 공간 (원본 1개 제외)"""
        if len(self.files) <= 1:
            return 0
        return self.total_size - self.files[0].size

    @property
    def count(self) -> int:
        """중복 파일 수"""
        return len(self.files)


class DuplicateFinder:
    """중복 파일 탐지 클래스"""

    def __init__(self, config: OrganizerConfig):
        self.config = config
        self._size_groups: Dict[int, List[Path]] = defaultdict(list)
        self._hash_cache: Dict[Path, str] = {}

    def _should_exclude(self, path: Path) -> bool:
        """파일/폴더 제외 여부 확인"""
        # 폴더 이름 체크
        for part in path.parts:
            if part in self.config.excluded_dirs:
                return True

        # 파일 패턴 체크
        for pattern in self.config.excluded_patterns:
            if fnmatch.fnmatch(path.name, pattern):
                return True

        return False

    def _calculate_hash(self, file_path: Path, chunk_size: int = 65536) -> Optional[str]:
        """
        파일의 SHA256 해시 계산

        Args:
            file_path: 파일 경로
            chunk_size: 읽기 청크 크기 (기본 64KB)

        Returns:
            SHA256 해시 문자열 또는 None (오류 시)
        """
        # 캐시 확인
        if file_path in self._hash_cache:
            return self._hash_cache[file_path]

        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(chunk_size), b''):
                    sha256_hash.update(chunk)

            hash_value = sha256_hash.hexdigest()
            self._hash_cache[file_path] = hash_value
            return hash_value

        except (IOError, OSError, PermissionError) as e:
            return None

    def _calculate_partial_hash(self, file_path: Path, sample_size: int = 4096) -> Optional[str]:
        """
        파일의 부분 해시 계산 (빠른 사전 필터링용)
        파일의 시작, 중간, 끝 부분만 해싱

        Args:
            file_path: 파일 경로
            sample_size: 각 부분에서 읽을 바이트 수

        Returns:
            부분 해시 문자열 또는 None
        """
        try:
            file_size = file_path.stat().st_size
            sha256_hash = hashlib.sha256()

            with open(file_path, 'rb') as f:
                # 시작 부분
                sha256_hash.update(f.read(sample_size))

                if file_size > sample_size * 3:
                    # 중간 부분
                    f.seek(file_size // 2)
                    sha256_hash.update(f.read(sample_size))

                    # 끝 부분
                    f.seek(-sample_size, 2)
                    sha256_hash.update(f.read(sample_size))

            return sha256_hash.hexdigest()

        except (IOError, OSError, PermissionError):
            return None

    def scan_directory(self, directory: Path) -> List[FileInfo]:
        """
        디렉토리를 재귀적으로 스캔하여 파일 정보 수집

        Args:
            directory: 스캔할 디렉토리 경로

        Returns:
            FileInfo 객체 리스트
        """
        files = []

        try:
            for item in directory.rglob('*'):
                if item.is_file() and not self._should_exclude(item):
                    try:
                        size = item.stat().st_size
                        if size >= self.config.min_file_size:
                            files.append(FileInfo(path=item, size=size))
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass

        return files

    def find_duplicates(self, directories: List[Path] = None) -> List[DuplicateGroup]:
        """
        지정된 디렉토리들에서 중복 파일 탐지

        Args:
            directories: 스캔할 디렉토리 리스트 (None이면 config에서 가져옴)

        Returns:
            DuplicateGroup 리스트
        """
        if directories is None:
            directories = self.config.target_directories

        # 1단계: 모든 파일 스캔 및 크기별 그룹화
        print("📁 파일 스캔 중...")
        all_files: List[FileInfo] = []
        for directory in directories:
            if directory.exists() and directory.is_dir():
                all_files.extend(self.scan_directory(directory))

        print(f"   총 {len(all_files):,}개 파일 발견")

        # 크기별 그룹화 (동일 크기 파일만 중복 후보)
        size_groups: Dict[int, List[FileInfo]] = defaultdict(list)
        for file_info in all_files:
            size_groups[file_info.size].append(file_info)

        # 크기가 같은 파일이 2개 이상인 그룹만 선택
        candidates = {size: files for size, files in size_groups.items() if len(files) > 1}
        candidate_count = sum(len(files) for files in candidates.values())
        print(f"   중복 후보: {candidate_count:,}개 파일 ({len(candidates):,}개 크기 그룹)")

        # 2단계: 부분 해시로 추가 필터링 (대용량 파일 최적화)
        print("🔍 해시 계산 중...")
        partial_hash_groups: Dict[Tuple[int, str], List[FileInfo]] = defaultdict(list)

        for size, files in candidates.items():
            for file_info in files:
                partial_hash = self._calculate_partial_hash(file_info.path)
                if partial_hash:
                    partial_hash_groups[(size, partial_hash)].append(file_info)

        # 부분 해시도 같은 파일만 전체 해시 계산
        final_candidates = {k: v for k, v in partial_hash_groups.items() if len(v) > 1}

        # 3단계: 전체 해시 계산 및 최종 중복 그룹 생성
        hash_groups: Dict[str, DuplicateGroup] = {}
        total_to_hash = sum(len(files) for files in final_candidates.values())
        hashed_count = 0

        for (size, partial_hash), files in final_candidates.items():
            for file_info in files:
                full_hash = self._calculate_hash(file_info.path)
                if full_hash:
                    file_info.hash = full_hash
                    if full_hash not in hash_groups:
                        hash_groups[full_hash] = DuplicateGroup(hash=full_hash)
                    hash_groups[full_hash].add_file(file_info)

                hashed_count += 1
                if hashed_count % 100 == 0:
                    print(f"   진행: {hashed_count:,}/{total_to_hash:,}")

        # 실제 중복인 그룹만 반환 (2개 이상 파일)
        duplicates = [group for group in hash_groups.values() if group.count > 1]

        # 낭비 공간 기준으로 정렬
        duplicates.sort(key=lambda g: g.wasted_space, reverse=True)

        total_wasted = sum(g.wasted_space for g in duplicates)
        print(f"✅ 중복 그룹 {len(duplicates):,}개 발견")
        print(f"   절약 가능한 공간: {self._format_size(total_wasted)}")

        return duplicates

    def find_duplicates_parallel(self, directories: List[Path] = None,
                                  max_workers: int = 4) -> List[DuplicateGroup]:
        """
        병렬 처리로 중복 파일 탐지 (대규모 디렉토리용)

        Args:
            directories: 스캔할 디렉토리 리스트
            max_workers: 최대 워커 스레드 수

        Returns:
            DuplicateGroup 리스트
        """
        if directories is None:
            directories = self.config.target_directories

        # 파일 스캔
        print("📁 파일 스캔 중...")
        all_files: List[FileInfo] = []
        for directory in directories:
            if directory.exists() and directory.is_dir():
                all_files.extend(self.scan_directory(directory))

        print(f"   총 {len(all_files):,}개 파일 발견")

        # 크기별 그룹화
        size_groups: Dict[int, List[FileInfo]] = defaultdict(list)
        for file_info in all_files:
            size_groups[file_info.size].append(file_info)

        candidates = [(size, files) for size, files in size_groups.items() if len(files) > 1]
        print(f"   중복 후보 그룹: {len(candidates):,}개")

        # 병렬 해시 계산
        print("🔍 병렬 해시 계산 중...")
        hash_groups: Dict[str, DuplicateGroup] = {}

        def process_file(file_info: FileInfo) -> Tuple[FileInfo, Optional[str]]:
            full_hash = self._calculate_hash(file_info.path)
            return file_info, full_hash

        files_to_hash = [f for _, files in candidates for f in files]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_file, f): f for f in files_to_hash}
            completed = 0

            for future in as_completed(futures):
                file_info, full_hash = future.result()
                if full_hash:
                    file_info.hash = full_hash
                    if full_hash not in hash_groups:
                        hash_groups[full_hash] = DuplicateGroup(hash=full_hash)
                    hash_groups[full_hash].add_file(file_info)

                completed += 1
                if completed % 100 == 0:
                    print(f"   진행: {completed:,}/{len(files_to_hash):,}")

        duplicates = [group for group in hash_groups.values() if group.count > 1]
        duplicates.sort(key=lambda g: g.wasted_space, reverse=True)

        return duplicates

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """바이트를 읽기 쉬운 형식으로 변환"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    def get_summary(self, duplicates: List[DuplicateGroup]) -> Dict:
        """
        중복 파일 분석 요약 정보 반환

        Args:
            duplicates: 중복 그룹 리스트

        Returns:
            요약 정보 딕셔너리
        """
        total_groups = len(duplicates)
        total_files = sum(g.count for g in duplicates)
        total_wasted = sum(g.wasted_space for g in duplicates)
        total_size = sum(g.total_size for g in duplicates)

        return {
            "duplicate_groups": total_groups,
            "total_duplicate_files": total_files,
            "total_wasted_space": total_wasted,
            "total_wasted_space_formatted": self._format_size(total_wasted),
            "total_size": total_size,
            "total_size_formatted": self._format_size(total_size),
            "potential_files_to_remove": total_files - total_groups,
        }
