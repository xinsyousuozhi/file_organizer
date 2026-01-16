"""
로깅 모듈: 파일 정리 작업의 상세 로깅
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class LogEntry:
    """로그 항목"""
    timestamp: str
    level: str
    action: str
    source: Optional[str] = None
    destination: Optional[str] = None
    status: str = ""
    details: Optional[Dict] = None
    error: Optional[str] = None


class FileOrganizerLogger:
    """파일 정리 전용 로거"""

    def __init__(self, log_dir: Path, session_name: str = None):
        """
        Args:
            log_dir: 로그 파일 저장 디렉토리
            session_name: 세션 이름 (None이면 자동 생성)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_name = session_name or self.session_id

        # 로그 파일 경로
        self.log_file = self.log_dir / f"organizer_{self.session_id}.log"
        self.json_log_file = self.log_dir / f"organizer_{self.session_id}.json"

        # Python 표준 로거 설정
        self._setup_logger()

        # JSON 로그 저장용 리스트
        self.entries: List[LogEntry] = []

        # 세션 시작 기록
        self.info("세션 시작", details={"session_id": self.session_id})

    def _setup_logger(self):
        """표준 로거 설정"""
        self.logger = logging.getLogger(f"FileOrganizer_{self.session_id}")
        self.logger.setLevel(logging.DEBUG)

        # 기존 핸들러 제거
        self.logger.handlers = []

        # 파일 핸들러
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 포맷 설정
        file_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_format = logging.Formatter('%(message)s')

        file_handler.setFormatter(file_format)
        console_handler.setFormatter(console_format)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _create_entry(self, level: str, action: str, **kwargs) -> LogEntry:
        """로그 항목 생성"""
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            action=action,
            **kwargs
        )
        self.entries.append(entry)
        return entry

    def _format_message(self, action: str, source: str = None,
                        destination: str = None, details: Dict = None) -> str:
        """로그 메시지 포맷팅"""
        parts = [action]
        if source:
            parts.append(f"| 원본: {source}")
        if destination:
            parts.append(f"| 대상: {destination}")
        if details:
            detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
            parts.append(f"| {detail_str}")
        return " ".join(parts)

    def debug(self, action: str, source: str = None, destination: str = None,
              details: Dict = None):
        """디버그 로그"""
        self._create_entry("DEBUG", action, source=source, destination=destination,
                          details=details)
        self.logger.debug(self._format_message(action, source, destination, details))

    def info(self, action: str, source: str = None, destination: str = None,
             details: Dict = None, status: str = ""):
        """정보 로그"""
        self._create_entry("INFO", action, source=source, destination=destination,
                          details=details, status=status)
        self.logger.info(self._format_message(action, source, destination, details))

    def warning(self, action: str, source: str = None, destination: str = None,
                details: Dict = None):
        """경고 로그"""
        self._create_entry("WARNING", action, source=source, destination=destination,
                          details=details)
        self.logger.warning(self._format_message(action, source, destination, details))

    def error(self, action: str, source: str = None, error: str = None,
              details: Dict = None):
        """오류 로그"""
        self._create_entry("ERROR", action, source=source, error=error,
                          details=details)
        msg = self._format_message(action, source, details=details)
        if error:
            msg += f" | 오류: {error}"
        self.logger.error(msg)

    def log_duplicate_found(self, group_id: int, files: List[str], hash_value: str):
        """중복 파일 발견 로그"""
        self.info(
            "중복 파일 그룹 발견",
            details={
                "group_id": group_id,
                "file_count": len(files),
                "hash": hash_value[:16] + "...",
            }
        )
        for file_path in files:
            self.debug("중복 파일 멤버", source=file_path)

    def log_version_group_found(self, base_name: str, files: List[str]):
        """버전 그룹 발견 로그"""
        self.info(
            "버전 그룹 발견",
            details={
                "base_name": base_name,
                "version_count": len(files),
            }
        )

    def log_classification(self, file_path: str, category: str,
                           confidence: float, keywords: List[str] = None):
        """파일 분류 로그"""
        self.debug(
            "파일 분류",
            source=file_path,
            details={
                "category": category,
                "confidence": f"{confidence:.2%}",
                "keywords": keywords[:5] if keywords else [],
            }
        )

    def log_file_move(self, source: str, destination: str, action: str,
                      reason: str, status: str, error: str = None):
        """파일 이동 로그"""
        if status == "success":
            self.info(
                f"파일 {action}",
                source=source,
                destination=destination,
                details={"reason": reason},
                status=status
            )
        elif status == "dry_run":
            self.info(
                f"[DRY RUN] 파일 {action} 예정",
                source=source,
                destination=destination,
                details={"reason": reason},
                status=status
            )
        else:
            self.error(
                f"파일 {action} 실패",
                source=source,
                error=error,
                details={"reason": reason}
            )

    def log_summary(self, summary: Dict):
        """요약 정보 로그"""
        self.info("=" * 50)
        self.info("작업 요약")
        for key, value in summary.items():
            self.info(f"  {key}: {value}")
        self.info("=" * 50)

    def save_json_log(self):
        """JSON 형식 로그 저장"""
        try:
            log_data = {
                "session_id": self.session_id,
                "session_name": self.session_name,
                "start_time": self.entries[0].timestamp if self.entries else None,
                "end_time": datetime.now().isoformat(),
                "total_entries": len(self.entries),
                "entries": [asdict(entry) for entry in self.entries],
            }

            with open(self.json_log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"JSON 로그 저장: {self.json_log_file}")

        except Exception as e:
            self.logger.error(f"JSON 로그 저장 실패: {e}")

    def finalize(self):
        """세션 종료 및 로그 저장"""
        self.info("세션 종료", details={"total_entries": len(self.entries)})
        self.save_json_log()

        # 핸들러 정리
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)

    def get_log_paths(self) -> Dict[str, Path]:
        """로그 파일 경로 반환"""
        return {
            "text_log": self.log_file,
            "json_log": self.json_log_file,
        }

    def get_statistics(self) -> Dict:
        """로그 통계 반환"""
        stats = {
            "total_entries": len(self.entries),
            "by_level": {},
            "by_action": {},
            "errors": [],
        }

        for entry in self.entries:
            # 레벨별 카운트
            level = entry.level
            stats["by_level"][level] = stats["by_level"].get(level, 0) + 1

            # 액션별 카운트
            action = entry.action
            stats["by_action"][action] = stats["by_action"].get(action, 0) + 1

            # 오류 수집
            if entry.level == "ERROR":
                stats["errors"].append({
                    "timestamp": entry.timestamp,
                    "action": entry.action,
                    "source": entry.source,
                    "error": entry.error,
                })

        return stats


def create_session_logger(base_dir: Path = None, session_name: str = None) -> FileOrganizerLogger:
    """
    새 세션 로거 생성 헬퍼 함수

    Args:
        base_dir: 로그 기본 디렉토리 (None이면 현재 디렉토리/_OrganizedFiles/logs)
        session_name: 세션 이름

    Returns:
        FileOrganizerLogger 인스턴스
    """
    if base_dir is None:
        base_dir = Path.home() / "_OrganizedFiles" / "logs"

    return FileOrganizerLogger(log_dir=base_dir, session_name=session_name)
