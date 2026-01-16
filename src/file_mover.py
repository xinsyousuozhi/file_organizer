"""
파일 이동 및 정리 모듈: 안전한 파일 이동, 아카이빙, 휴지통 이동
"""

import os
import shutil
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .config import OrganizerConfig
from .duplicate_finder import FileInfo, DuplicateGroup
from .classifier import ClassificationResult


class MoveAction(Enum):
    """파일 이동 액션 유형"""
    MOVE = "move"
    COPY = "copy"
    ARCHIVE = "archive"
    RECYCLE = "recycle"


@dataclass
class MoveOperation:
    """파일 이동 작업 정보"""
    source: Path
    destination: Path
    action: MoveAction
    reason: str = ""
    status: str = "pending"  # pending, success, failed, skipped
    error_message: str = ""
    size: int = 0


class FileMover:
    """파일 이동 클래스"""

    def __init__(self, config: OrganizerConfig, logger=None):
        self.config = config
        self.logger = logger
        self.operations: List[MoveOperation] = []
        self._move_history: List[MoveOperation] = []

    def _log(self, message: str, level: str = "INFO"):
        """로깅 헬퍼"""
        if self.logger:
            log_func = getattr(self.logger, level.lower(), self.logger.info)
            log_func(message)

    def _ensure_directory(self, path: Path) -> bool:
        """
        디렉토리 존재 확인 및 생성

        Args:
            path: 디렉토리 경로

        Returns:
            성공 여부
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except (OSError, PermissionError) as e:
            self._log(f"디렉토리 생성 실패: {path} - {e}", "ERROR")
            return False

    def _get_unique_path(self, path: Path) -> Path:
        """
        충돌 방지를 위한 고유 경로 생성

        Args:
            path: 원본 경로

        Returns:
            고유한 경로
        """
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1

        while True:
            new_name = f"{stem}_{counter}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1

    def _move_to_recycle_bin(self, file_path: Path) -> bool:
        """
        파일을 시스템 휴지통으로 이동

        Args:
            file_path: 파일 경로

        Returns:
            성공 여부
        """
        try:
            # Windows
            if platform.system() == "Windows":
                try:
                    from send2trash import send2trash
                    send2trash(str(file_path))
                    return True
                except ImportError:
                    # send2trash가 없으면 아카이브 폴더로 대체
                    self._log("send2trash 미설치, 아카이브 폴더로 이동합니다.", "WARNING")
                    return False

            # macOS/Linux
            else:
                try:
                    from send2trash import send2trash
                    send2trash(str(file_path))
                    return True
                except ImportError:
                    return False

        except Exception as e:
            self._log(f"휴지통 이동 실패: {file_path} - {e}", "ERROR")
            return False

    def plan_duplicate_cleanup(self, duplicates: List[DuplicateGroup],
                               keep_strategy: str = "newest") -> List[MoveOperation]:
        """
        중복 파일 정리 계획 수립

        Args:
            duplicates: 중복 그룹 리스트
            keep_strategy: 보존 전략 ('newest', 'oldest', 'largest', 'smallest')

        Returns:
            이동 작업 리스트
        """
        operations = []

        for group in duplicates:
            # 보존할 파일 선택
            files = sorted(group.files, key=lambda f: f.modified_time, reverse=True)

            if keep_strategy == "oldest":
                files = sorted(group.files, key=lambda f: f.modified_time)
            elif keep_strategy == "largest":
                files = sorted(group.files, key=lambda f: f.size, reverse=True)
            elif keep_strategy == "smallest":
                files = sorted(group.files, key=lambda f: f.size)

            # 첫 번째 파일 보존, 나머지 아카이브
            keep_file = files[0]
            archive_files = files[1:]

            for file_info in archive_files:
                # 아카이브 경로 생성
                relative_path = file_info.path.name
                archive_path = self.config.duplicates_archive / relative_path
                archive_path = self._get_unique_path(archive_path)

                action = MoveAction.RECYCLE if self.config.use_recycle_bin else MoveAction.ARCHIVE

                op = MoveOperation(
                    source=file_info.path,
                    destination=archive_path,
                    action=action,
                    reason=f"중복 파일 (원본: {keep_file.path.name})",
                    size=file_info.size
                )
                operations.append(op)

        self.operations.extend(operations)
        return operations

    def plan_classification_organize(self, results: List[ClassificationResult],
                                     base_path: Path = None) -> List[MoveOperation]:
        """
        분류 결과에 따른 정리 계획 수립

        Args:
            results: 분류 결과 리스트
            base_path: 기준 경로 (None이면 config에서 가져옴)

        Returns:
            이동 작업 리스트
        """
        if base_path is None:
            base_path = self.config.organized_archive

        operations = []

        for result in results:
            if result.target_path is None:
                continue

            # 원본과 대상이 같으면 스킵
            if result.file_info.path == result.target_path:
                continue

            # 고유 경로 확보
            target_path = self._get_unique_path(result.target_path)

            op = MoveOperation(
                source=result.file_info.path,
                destination=target_path,
                action=MoveAction.MOVE,
                reason=f"분류: {result.category}",
                size=result.file_info.size
            )
            operations.append(op)

        self.operations.extend(operations)
        return operations

    def plan_version_cleanup(self, keep_paths: List[Path],
                             archive_paths: List[Path]) -> List[MoveOperation]:
        """
        버전 파일 정리 계획 수립

        Args:
            keep_paths: 보존할 파일 경로 리스트
            archive_paths: 아카이브할 파일 경로 리스트

        Returns:
            이동 작업 리스트
        """
        operations = []

        for file_path in archive_paths:
            if not file_path.exists():
                continue

            archive_dest = self.config.archive_base / "Versions" / file_path.name
            archive_dest = self._get_unique_path(archive_dest)

            action = MoveAction.RECYCLE if self.config.use_recycle_bin else MoveAction.ARCHIVE

            op = MoveOperation(
                source=file_path,
                destination=archive_dest,
                action=action,
                reason="이전 버전 파일",
                size=file_path.stat().st_size if file_path.exists() else 0
            )
            operations.append(op)

        self.operations.extend(operations)
        return operations

    def execute_operations(self, operations: List[MoveOperation] = None,
                           dry_run: bool = None) -> Dict:
        """
        계획된 작업 실행

        Args:
            operations: 실행할 작업 리스트 (None이면 self.operations 사용)
            dry_run: 드라이 런 모드 (None이면 config에서 가져옴)

        Returns:
            실행 결과 요약
        """
        if operations is None:
            operations = self.operations

        if dry_run is None:
            dry_run = self.config.dry_run

        results = {
            "total": len(operations),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "dry_run": dry_run,
            "space_freed": 0,
            "errors": [],
        }

        for i, op in enumerate(operations):
            if dry_run:
                # 드라이 런: 실제 작업 없이 상태만 기록
                op.status = "dry_run"
                results["success"] += 1
                results["space_freed"] += op.size
                self._log(f"[DRY RUN] {op.action.value}: {op.source} -> {op.destination}")
                continue

            try:
                # 실제 작업 수행
                if op.action == MoveAction.RECYCLE:
                    if self._move_to_recycle_bin(op.source):
                        op.status = "success"
                        results["success"] += 1
                        results["space_freed"] += op.size
                    else:
                        # 휴지통 실패시 아카이브로 대체
                        op.action = MoveAction.ARCHIVE
                        self._execute_move(op)
                        if op.status == "success":
                            results["success"] += 1
                            results["space_freed"] += op.size
                        else:
                            results["failed"] += 1
                            results["errors"].append({
                                "file": str(op.source),
                                "error": op.error_message
                            })

                elif op.action in (MoveAction.MOVE, MoveAction.ARCHIVE):
                    self._execute_move(op)
                    if op.status == "success":
                        results["success"] += 1
                        if op.action == MoveAction.ARCHIVE:
                            results["space_freed"] += op.size
                    else:
                        results["failed"] += 1
                        results["errors"].append({
                            "file": str(op.source),
                            "error": op.error_message
                        })

                elif op.action == MoveAction.COPY:
                    self._execute_copy(op)
                    if op.status == "success":
                        results["success"] += 1
                    else:
                        results["failed"] += 1

            except Exception as e:
                op.status = "failed"
                op.error_message = str(e)
                results["failed"] += 1
                results["errors"].append({
                    "file": str(op.source),
                    "error": str(e)
                })
                self._log(f"작업 실패: {op.source} - {e}", "ERROR")

            # 진행 상황 출력
            if (i + 1) % 50 == 0:
                print(f"   진행: {i + 1}/{len(operations)}")

            # 이력 기록
            self._move_history.append(op)

        return results

    def _execute_move(self, op: MoveOperation):
        """실제 파일 이동 수행"""
        try:
            # 대상 디렉토리 생성
            if not self._ensure_directory(op.destination.parent):
                op.status = "failed"
                op.error_message = "대상 디렉토리 생성 실패"
                return

            # 파일 이동
            shutil.move(str(op.source), str(op.destination))
            op.status = "success"
            self._log(f"이동 완료: {op.source} -> {op.destination}")

        except (shutil.Error, OSError, PermissionError) as e:
            op.status = "failed"
            op.error_message = str(e)
            self._log(f"이동 실패: {op.source} - {e}", "ERROR")

    def _execute_copy(self, op: MoveOperation):
        """실제 파일 복사 수행"""
        try:
            if not self._ensure_directory(op.destination.parent):
                op.status = "failed"
                op.error_message = "대상 디렉토리 생성 실패"
                return

            shutil.copy2(str(op.source), str(op.destination))
            op.status = "success"
            self._log(f"복사 완료: {op.source} -> {op.destination}")

        except (shutil.Error, OSError, PermissionError) as e:
            op.status = "failed"
            op.error_message = str(e)
            self._log(f"복사 실패: {op.source} - {e}", "ERROR")

    def get_dry_run_report(self, operations: List[MoveOperation] = None) -> str:
        """
        드라이 런 결과 보고서 생성

        Args:
            operations: 작업 리스트

        Returns:
            포맷된 보고서
        """
        if operations is None:
            operations = self.operations

        lines = []
        lines.append("=" * 70)
        lines.append("🔍 드라이 런 (Dry Run) 미리보기")
        lines.append("=" * 70)
        lines.append(f"\n총 {len(operations)}개 파일 작업 예정\n")

        # 액션별 그룹화
        by_action: Dict[MoveAction, List[MoveOperation]] = {}
        for op in operations:
            if op.action not in by_action:
                by_action[op.action] = []
            by_action[op.action].append(op)

        total_size = 0

        for action, ops in by_action.items():
            action_name = {
                MoveAction.MOVE: "📦 이동",
                MoveAction.COPY: "📋 복사",
                MoveAction.ARCHIVE: "📁 아카이브",
                MoveAction.RECYCLE: "🗑️ 휴지통",
            }.get(action, action.value)

            lines.append(f"\n{action_name} ({len(ops)}개 파일)")
            lines.append("-" * 60)

            for op in ops[:20]:  # 상위 20개만 표시
                size_str = self._format_size(op.size)
                lines.append(f"  원본: {op.source}")
                lines.append(f"  대상: {op.destination}")
                lines.append(f"  크기: {size_str} | 사유: {op.reason}")
                lines.append("")
                total_size += op.size

            if len(ops) > 20:
                lines.append(f"  ... 외 {len(ops) - 20}개 파일")

        lines.append("\n" + "=" * 70)
        lines.append(f"예상 절약/이동 용량: {self._format_size(total_size)}")
        lines.append("=" * 70)
        lines.append("\n⚠️  이것은 미리보기입니다. 실제 파일은 변경되지 않았습니다.")
        lines.append("    실제 실행하려면 --execute 옵션을 사용하세요.")

        return "\n".join(lines)

    def get_execution_report(self, results: Dict) -> str:
        """
        실행 결과 보고서 생성

        Args:
            results: 실행 결과 딕셔너리

        Returns:
            포맷된 보고서
        """
        lines = []
        lines.append("=" * 70)
        lines.append("✅ 파일 정리 실행 결과")
        lines.append("=" * 70)

        if results["dry_run"]:
            lines.append("\n[드라이 런 모드 - 실제 파일 변경 없음]")

        lines.append(f"\n총 작업: {results['total']}개")
        lines.append(f"  성공: {results['success']}개")
        lines.append(f"  실패: {results['failed']}개")
        lines.append(f"  건너뜀: {results['skipped']}개")
        lines.append(f"\n절약된 공간: {self._format_size(results['space_freed'])}")

        if results["errors"]:
            lines.append(f"\n⚠️  오류 발생 ({len(results['errors'])}개):")
            for err in results["errors"][:10]:
                lines.append(f"  - {err['file']}")
                lines.append(f"    오류: {err['error']}")

        lines.append("\n" + "=" * 70)

        return "\n".join(lines)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """바이트를 읽기 쉬운 형식으로 변환"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    def clear_operations(self):
        """대기 중인 작업 초기화"""
        self.operations = []

    def get_history(self) -> List[MoveOperation]:
        """실행 이력 반환"""
        return self._move_history
