"""
메인 애플리케이션 모듈: 모든 기능을 통합한 FileOrganizer 클래스
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from .config import OrganizerConfig
from .duplicate_finder import DuplicateFinder, DuplicateGroup, FileInfo
from .version_manager import VersionManager, VersionGroup
from .classifier import FileClassifier, ClassificationResult
from .file_mover import FileMover, MoveOperation
from .logger import FileOrganizerLogger, create_session_logger


class FileOrganizer:
    """
    파일 정리 통합 클래스

    중복 파일 제거, 버전 관리, 지능형 분류 기능을 통합 제공
    """

    def __init__(self, config: OrganizerConfig = None, logger: FileOrganizerLogger = None, llm_config=None):
        """
        Args:
            config: 설정 객체 (None이면 기본 설정 사용)
            logger: 로거 객체 (None이면 자동 생성)
            llm_config: LLM 설정 객체 (None이면 LLM 사용 안 함)
        """
        self.config = config or OrganizerConfig()
        self.logger = logger or create_session_logger(self.config.archive_base / "logs")

        # 모듈 초기화
        self.duplicate_finder = DuplicateFinder(self.config)
        self.version_manager = VersionManager(self.config)
        self.classifier = FileClassifier(self.config, llm_config=llm_config)
        self.file_mover = FileMover(self.config, self.logger)

        # 스캔된 파일 캐시
        self._scanned_files: List[FileInfo] = []
        self._duplicates: List[DuplicateGroup] = []
        self._version_groups: List[VersionGroup] = []
        self._classifications: List[ClassificationResult] = []

    def scan_directories(self, directories: List[Path] = None) -> List[FileInfo]:
        """
        지정된 디렉토리들의 파일 스캔

        Args:
            directories: 스캔할 디렉토리 리스트 (None이면 config에서 가져옴)

        Returns:
            FileInfo 리스트
        """
        if directories is None:
            directories = self.config.target_directories

        self._scanned_files = []

        self.logger.info(f"디렉토리 스캔 시작", details={"count": len(directories)})

        for directory in directories:
            if directory.exists() and directory.is_dir():
                files = self.duplicate_finder.scan_directory(directory)
                self._scanned_files.extend(files)
                self.logger.info(f"디렉토리 스캔 완료",
                                details={"path": str(directory), "files": len(files)})

        self.logger.info(f"전체 스캔 완료", details={"total_files": len(self._scanned_files)})

        return self._scanned_files

    def find_duplicates(self, parallel: bool = False) -> List[DuplicateGroup]:
        """
        중복 파일 탐지

        Args:
            parallel: 병렬 처리 여부

        Returns:
            DuplicateGroup 리스트
        """
        self.logger.info("중복 파일 탐지 시작")

        if parallel:
            self._duplicates = self.duplicate_finder.find_duplicates_parallel(
                self.config.target_directories
            )
        else:
            self._duplicates = self.duplicate_finder.find_duplicates(
                self.config.target_directories
            )

        summary = self.duplicate_finder.get_summary(self._duplicates)
        self.logger.info("중복 파일 탐지 완료", details=summary)

        # 각 그룹 로깅
        for i, group in enumerate(self._duplicates):
            self.logger.log_duplicate_found(
                group_id=i,
                files=[str(f.path) for f in group.files],
                hash_value=group.hash
            )

        return self._duplicates

    def find_version_groups(self, files: List[FileInfo] = None) -> List[VersionGroup]:
        """
        버전 파일 그룹 탐지

        Args:
            files: 분석할 파일 리스트 (None이면 스캔된 파일 사용)

        Returns:
            VersionGroup 리스트
        """
        if files is None:
            if not self._scanned_files:
                self.scan_directories()
            files = self._scanned_files

        self.logger.info("버전 그룹 탐지 시작", details={"files": len(files)})

        self._version_groups = self.version_manager.find_version_groups(files)

        self.logger.info("버전 그룹 탐지 완료", details={"groups": len(self._version_groups)})

        for group in self._version_groups:
            self.logger.log_version_group_found(
                group.base_name,
                [str(f.path) for f in group.files]
            )

        return self._version_groups

    def classify_files(self, files: List[FileInfo] = None,
                       by_content: bool = True,
                       by_date: bool = True,
                       exclude_duplicates: bool = True,
                       keep_strategy: str = "newest") -> List[ClassificationResult]:
        """
        파일 분류

        Args:
            files: 분류할 파일 리스트 (None이면 스캔된 파일 사용)
            by_content: 내용 기반 분류 여부
            by_date: 날짜 기반 분류 여부
            exclude_duplicates: 중복 파일 제외 여부 (보존 대상만 포함)
            keep_strategy: 중복 보존 전략 ('newest', 'oldest', 'largest', 'smallest')

        Returns:
            ClassificationResult 리스트
        """
        if files is None:
            if not self._scanned_files:
                self.scan_directories()
            files = self._scanned_files

        # 중복 파일 제외 처리: 중복 그룹에서 제외 대상 파일만 분류에서 제외
        if exclude_duplicates and self._duplicates:
            # 그룹별로 제외할 파일만 선택
            exclude_paths = set()

            for group in self._duplicates:
                files_sorted = group.files
                if keep_strategy == "newest":
                    files_sorted = sorted(group.files, key=lambda f: f.modified_time, reverse=True)
                elif keep_strategy == "oldest":
                    files_sorted = sorted(group.files, key=lambda f: f.modified_time)
                elif keep_strategy == "largest":
                    files_sorted = sorted(group.files, key=lambda f: f.size, reverse=True)
                elif keep_strategy == "smallest":
                    files_sorted = sorted(group.files, key=lambda f: f.size)

                # 첫 번째 파일은 보존, 나머지는 제외
                if files_sorted:
                    for f in files_sorted[1:]:
                        exclude_paths.add(f.path)

            # 실제 분류 대상 필터링 (제외 대상만 걸러냄)
            files = [f for f in files if f.path not in exclude_paths]

        self.logger.info("파일 분류 시작",
                        details={"files": len(files), "by_content": by_content, "by_date": by_date})

        self._classifications = self.classifier.classify_files(files, by_content, by_date)

        # 대상 경로 생성
        for result in self._classifications:
            self.classifier.generate_target_path(result, self.config.organized_archive)

        summary = self.classifier.get_classification_summary(self._classifications)
        self.logger.info("파일 분류 완료", details={"categories": len(summary["by_category"])})

        return self._classifications

    def plan_cleanup(self, duplicates: bool = True,
                     versions: bool = False,
                     organize: bool = False,
                     keep_strategy: str = "newest") -> List[MoveOperation]:
        """
        정리 작업 계획 수립

        Args:
            duplicates: 중복 파일 정리 포함
            versions: 버전 파일 정리 포함
            organize: 파일 분류 정리 포함
            keep_strategy: 보존 전략

        Returns:
            MoveOperation 리스트
        """
        self.file_mover.clear_operations()
        operations = []

        if duplicates and self._duplicates:
            ops = self.file_mover.plan_duplicate_cleanup(
                self._duplicates, keep_strategy
            )
            operations.extend(ops)
            self.logger.info(f"중복 파일 정리 계획", details={"operations": len(ops)})

        if versions and self._version_groups:
            keep_paths = []
            archive_paths = []
            for group in self._version_groups:
                analysis = self.version_manager.analyze_version_group(group)
                if analysis['recommended_keep']:
                    keep_paths.append(Path(analysis['recommended_keep']))
                for path in analysis['recommended_archive']:
                    archive_paths.append(Path(path))

            ops = self.file_mover.plan_version_cleanup(keep_paths, archive_paths)
            operations.extend(ops)
            self.logger.info(f"버전 파일 정리 계획", details={"operations": len(ops)})

        if organize and self._classifications:
            ops = self.file_mover.plan_classification_organize(
                self._classifications, self.config.organized_archive
            )
            operations.extend(ops)
            self.logger.info(f"파일 분류 정리 계획", details={"operations": len(ops)})

        return operations

    def execute(self, dry_run: bool = None) -> Dict:
        """
        계획된 작업 실행

        Args:
            dry_run: 드라이 런 여부 (None이면 config 설정 사용)

        Returns:
            실행 결과 딕셔너리
        """
        if dry_run is None:
            dry_run = self.config.dry_run

        operations = self.file_mover.operations

        self.logger.info("작업 실행 시작",
                        details={"operations": len(operations), "dry_run": dry_run})

        results = self.file_mover.execute_operations(dry_run=dry_run)

        self.logger.log_summary(results)

        return results

    def get_dry_run_report(self) -> str:
        """드라이 런 보고서 반환"""
        return self.file_mover.get_dry_run_report()

    def get_execution_report(self, results: Dict) -> str:
        """실행 결과 보고서 반환"""
        return self.file_mover.get_execution_report(results)

    def get_statistics(self) -> Dict:
        """
        현재 분석 결과 통계 반환
        """
        stats = {
            "scanned_files": len(self._scanned_files),
            "duplicate_groups": len(self._duplicates),
            "version_groups": len(self._version_groups),
            "classified_files": len(self._classifications),
            "pending_operations": len(self.file_mover.operations),
        }

        if self._duplicates:
            dup_summary = self.duplicate_finder.get_summary(self._duplicates)
            stats["duplicates"] = dup_summary

        if self._classifications:
            class_summary = self.classifier.get_classification_summary(self._classifications)
            stats["classifications"] = class_summary

        return stats

    def finalize(self):
        """세션 종료 및 리소스 정리"""
        self.logger.finalize()


def quick_scan(directory: Path, find_duplicates: bool = True,
               find_versions: bool = False) -> Dict:
    """
    빠른 스캔 유틸리티 함수

    Args:
        directory: 스캔할 디렉토리
        find_duplicates: 중복 파일 탐지 여부
        find_versions: 버전 그룹 탐지 여부

    Returns:
        분석 결과 딕셔너리
    """
    config = OrganizerConfig(target_directories=[directory])
    organizer = FileOrganizer(config)

    results = {
        "directory": str(directory),
        "scanned_files": 0,
    }

    try:
        files = organizer.scan_directories()
        results["scanned_files"] = len(files)

        if find_duplicates:
            duplicates = organizer.find_duplicates()
            results["duplicates"] = organizer.duplicate_finder.get_summary(duplicates)

        if find_versions:
            versions = organizer.find_version_groups()
            results["version_groups"] = len(versions)

    finally:
        organizer.finalize()

    return results
