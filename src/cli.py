"""
CLI 인터페이스 모듈: 명령줄 인터페이스 및 사용자 상호작용
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

from .config import OrganizerConfig
from .duplicate_finder import DuplicateFinder, DuplicateGroup, FileInfo
from .version_manager import VersionManager, VersionGroup, format_version_report
from .classifier import FileClassifier, ClassificationResult, format_classification_report
from .file_mover import FileMover, MoveOperation
from .logger import FileOrganizerLogger, create_session_logger


def print_banner():
    """프로그램 배너 출력"""
    banner = """
╔══════════════════════════════════════════════════════════════════════╗
║                    📁 파일 정리 도구 (File Organizer)                    ║
║                              v1.0.0                                    ║
╚══════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_section(title: str):
    """섹션 헤더 출력"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def format_size(size_bytes: int) -> str:
    """바이트를 읽기 쉬운 형식으로 변환"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def prompt_user(message: str, choices: List[str] = None, default: str = None) -> str:
    """
    사용자 입력 프롬프트

    Args:
        message: 표시할 메시지
        choices: 선택지 리스트
        default: 기본값

    Returns:
        사용자 입력
    """
    if choices:
        choice_str = "/".join(choices)
        if default:
            message = f"{message} [{choice_str}] (기본: {default}): "
        else:
            message = f"{message} [{choice_str}]: "
    elif default:
        message = f"{message} (기본: {default}): "
    else:
        message = f"{message}: "

    response = input(message).strip()

    if not response and default:
        return default

    if choices and response.lower() not in [c.lower() for c in choices]:
        print(f"  잘못된 선택입니다. {choices} 중에서 선택하세요.")
        return prompt_user(message.split('[')[0].strip(), choices, default)

    return response


def interactive_duplicate_review(duplicates: List[DuplicateGroup],
                                  mover: FileMover,
                                  config: OrganizerConfig) -> List[MoveOperation]:
    """
    중복 파일 대화형 검토

    Args:
        duplicates: 중복 그룹 리스트
        mover: FileMover 인스턴스
        config: 설정

    Returns:
        계획된 작업 리스트
    """
    operations = []

    print_section("중복 파일 검토")
    print(f"\n총 {len(duplicates)}개 중복 그룹이 발견되었습니다.\n")

    mode = prompt_user(
        "검토 모드를 선택하세요\n"
        "  a: 자동 처리 (최신 파일 보존)\n"
        "  i: 각 그룹 개별 검토\n"
        "  s: 건너뛰기",
        choices=["a", "i", "s"],
        default="a"
    )

    if mode.lower() == "s":
        print("  중복 파일 처리를 건너뜁니다.")
        return operations

    if mode.lower() == "a":
        # 자동 처리
        return mover.plan_duplicate_cleanup(duplicates, keep_strategy="newest")

    # 개별 검토
    for i, group in enumerate(duplicates):
        print(f"\n{'─'*50}")
        print(f"그룹 {i+1}/{len(duplicates)}")
        print(f"해시: {group.hash[:16]}...")
        print(f"파일 수: {group.count}개")
        print(f"낭비 공간: {format_size(group.wasted_space)}")
        print("")

        # 파일 목록 표시
        sorted_files = sorted(group.files, key=lambda f: f.modified_time, reverse=True)
        for j, file_info in enumerate(sorted_files):
            modified = datetime.fromtimestamp(file_info.modified_time)
            marker = "[최신]" if j == 0 else ""
            print(f"  {j+1}. {file_info.path.name} {marker}")
            print(f"     경로: {file_info.path.parent}")
            print(f"     수정일: {modified.strftime('%Y-%m-%d %H:%M')}")
            print(f"     크기: {format_size(file_info.size)}")
            print("")

        choice = prompt_user(
            "작업을 선택하세요\n"
            "  k: 최신 파일 보존, 나머지 아카이브\n"
            "  숫자: 해당 번호 파일 보존\n"
            "  s: 이 그룹 건너뛰기\n"
            "  q: 검토 종료",
            default="k"
        )

        if choice.lower() == "q":
            break
        elif choice.lower() == "s":
            continue
        elif choice.lower() == "k":
            keep_idx = 0
        else:
            try:
                keep_idx = int(choice) - 1
                if keep_idx < 0 or keep_idx >= len(sorted_files):
                    print("  잘못된 번호입니다. 최신 파일을 보존합니다.")
                    keep_idx = 0
            except ValueError:
                print("  잘못된 입력입니다. 최신 파일을 보존합니다.")
                keep_idx = 0

        # 작업 생성
        keep_file = sorted_files[keep_idx]
        for j, file_info in enumerate(sorted_files):
            if j != keep_idx:
                dest = config.duplicates_archive / file_info.path.name
                from .file_mover import MoveAction
                op = MoveOperation(
                    source=file_info.path,
                    destination=dest,
                    action=MoveAction.ARCHIVE,
                    reason=f"중복 파일 (보존: {keep_file.path.name})",
                    size=file_info.size
                )
                operations.append(op)

        print(f"  ✓ {keep_file.path.name} 보존, {len(sorted_files)-1}개 파일 아카이브 예정")

    return operations


def interactive_version_review(groups: List[VersionGroup],
                                manager: VersionManager,
                                config: OrganizerConfig) -> List[MoveOperation]:
    """
    버전 파일 대화형 검토

    Args:
        groups: 버전 그룹 리스트
        manager: VersionManager 인스턴스
        config: 설정

    Returns:
        계획된 작업 리스트
    """
    operations = []

    print_section("버전 파일 검토")
    print(f"\n총 {len(groups)}개 버전 그룹이 발견되었습니다.\n")

    mode = prompt_user(
        "검토 모드를 선택하세요\n"
        "  a: 자동 처리 (최신/최종본 보존)\n"
        "  r: 보고서만 보기\n"
        "  s: 건너뛰기",
        choices=["a", "r", "s"],
        default="r"
    )

    if mode.lower() == "s":
        print("  버전 파일 처리를 건너뜁니다.")
        return operations

    if mode.lower() == "r":
        # 보고서 출력
        report = format_version_report(groups, manager)
        print(report)
        return operations

    # 자동 처리
    from .file_mover import FileMover

    keep_paths = []
    archive_paths = []

    for group in groups:
        analysis = manager.analyze_version_group(group)
        if analysis['recommended_keep']:
            keep_paths.append(Path(analysis['recommended_keep']))
        for path in analysis['recommended_archive']:
            archive_paths.append(Path(path))

    print(f"\n  보존: {len(keep_paths)}개 파일")
    print(f"  아카이브: {len(archive_paths)}개 파일")

    mover = FileMover(config)
    return mover.plan_version_cleanup(keep_paths, archive_paths)


def run_cli():
    """CLI 메인 함수"""
    parser = argparse.ArgumentParser(
        description="로컬 파일 지능형 정리 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  %(prog)s --target ~/Documents
  %(prog)s --target ~/Downloads --archive ~/Backup --dry-run
  %(prog)s --target D:\\Files --find-duplicates --execute
  %(prog)s --target /mnt/drive --classify --by-date
        """
    )

    # 필수 인자
    parser.add_argument(
        "--target", "-t",
        type=str,
        nargs="+",
        required=True,
        help="정리할 대상 폴더 경로 (여러 개 지정 가능)"
    )

    # 아카이브 설정
    parser.add_argument(
        "--archive", "-a",
        type=str,
        default=None,
        help="아카이브 폴더 경로 (기본: 홈폴더/_OrganizedFiles)"
    )

    # 작업 모드
    parser.add_argument(
        "--find-duplicates", "-d",
        action="store_true",
        help="중복 파일 탐지"
    )

    parser.add_argument(
        "--find-versions", "-v",
        action="store_true",
        help="버전 파일 그룹 탐지"
    )

    parser.add_argument(
        "--classify", "-c",
        action="store_true",
        help="파일 분류 (주제/날짜 기반)"
    )

    parser.add_argument(
        "--by-content",
        action="store_true",
        help="내용 기반 분류 활성화"
    )

    parser.add_argument(
        "--by-date",
        action="store_true",
        help="날짜 기반 분류 활성화"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="모든 기능 실행 (중복, 버전, 분류)"
    )

    # 실행 옵션
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="드라이 런 모드 (미리보기만, 기본값)"
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="실제 파일 이동 실행"
    )

    parser.add_argument(
        "--use-recycle-bin",
        action="store_true",
        help="휴지통 사용 (아카이브 대신)"
    )

    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="대화형 모드"
    )

    # 기타 옵션
    parser.add_argument(
        "--keep-strategy",
        choices=["newest", "oldest", "largest", "smallest"],
        default="newest",
        help="중복 파일 보존 전략 (기본: newest)"
    )

    parser.add_argument(
        "--min-size",
        type=int,
        default=1,
        help="최소 파일 크기 (바이트, 기본: 1)"
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        help="병렬 처리 활성화"
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="최소 출력"
    )

    args = parser.parse_args()

    # 작업 모드 확인
    if not any([args.find_duplicates, args.find_versions, args.classify, args.all]):
        print("오류: 최소한 하나의 작업 모드를 지정해야 합니다.")
        print("  --find-duplicates, --find-versions, --classify, 또는 --all")
        parser.print_help()
        sys.exit(1)

    # 설정 초기화
    target_dirs = [Path(p).resolve() for p in args.target]
    for path in target_dirs:
        if not path.exists():
            print(f"오류: 대상 경로가 존재하지 않습니다: {path}")
            sys.exit(1)

    config = OrganizerConfig(
        target_directories=target_dirs,
        dry_run=not args.execute,
        use_recycle_bin=args.use_recycle_bin,
        min_file_size=args.min_size,
    )

    if args.archive:
        config.archive_base = Path(args.archive).resolve()
        config.duplicates_archive = config.archive_base / "Duplicates"
        config.organized_archive = config.archive_base / "Organized"

    # 배너 출력
    if not args.quiet:
        print_banner()
        print(f"대상 폴더: {', '.join(str(p) for p in target_dirs)}")
        print(f"아카이브 폴더: {config.archive_base}")
        print(f"드라이 런: {'예' if config.dry_run else '아니오 (실제 실행)'}")
        print("")

    # 로거 초기화
    logger = create_session_logger(config.archive_base / "logs")

    # FileMover 초기화
    mover = FileMover(config, logger)

    # 작업 실행
    all_operations: List[MoveOperation] = []

    try:
        # 중복 파일 탐지
        if args.find_duplicates or args.all:
            print_section("중복 파일 탐지")

            finder = DuplicateFinder(config)

            if args.parallel:
                duplicates = finder.find_duplicates_parallel(target_dirs)
            else:
                duplicates = finder.find_duplicates(target_dirs)

            if duplicates:
                summary = finder.get_summary(duplicates)
                print(f"\n📊 요약:")
                print(f"   중복 그룹: {summary['duplicate_groups']}개")
                print(f"   중복 파일: {summary['total_duplicate_files']}개")
                print(f"   절약 가능: {summary['total_wasted_space_formatted']}")

                if args.interactive:
                    ops = interactive_duplicate_review(duplicates, mover, config)
                else:
                    ops = mover.plan_duplicate_cleanup(duplicates, args.keep_strategy)

                all_operations.extend(ops)
                logger.info(f"중복 파일 처리 계획: {len(ops)}개 작업")
            else:
                print("\n  중복 파일이 없습니다.")

        # 버전 파일 탐지
        if args.find_versions or args.all:
            print_section("버전 파일 탐지")

            finder = DuplicateFinder(config)
            all_files = []
            for directory in target_dirs:
                all_files.extend(finder.scan_directory(directory))

            version_mgr = VersionManager(config)
            version_groups = version_mgr.find_version_groups(all_files)

            if version_groups:
                print(f"\n📊 요약:")
                print(f"   버전 그룹: {len(version_groups)}개")

                if args.interactive:
                    ops = interactive_version_review(version_groups, version_mgr, config)
                else:
                    report = format_version_report(version_groups, version_mgr)
                    print(report)
                    # 자동 모드에서는 기본적으로 처리하지 않음
                    ops = []

                all_operations.extend(ops)
            else:
                print("\n  버전 그룹이 없습니다.")

        # 파일 분류
        if args.classify or args.all:
            print_section("파일 분류")

            finder = DuplicateFinder(config)
            all_files = []
            for directory in target_dirs:
                all_files.extend(finder.scan_directory(directory))

            classifier = FileClassifier(config)

            by_content = args.by_content or (not args.by_date and not args.by_content)
            by_date = args.by_date or (not args.by_date and not args.by_content)

            print(f"   분류 기준: {'내용' if by_content else ''} {'날짜' if by_date else ''}")
            print(f"   분석 대상: {len(all_files)}개 파일")

            results = classifier.classify_files(all_files, by_content=by_content, by_date=by_date)

            # 대상 경로 생성
            for result in results:
                classifier.generate_target_path(result, config.organized_archive)

            summary = classifier.get_classification_summary(results)
            report = format_classification_report(summary)
            print(report)

            # 분류 결과에 따른 이동 작업
            ops = mover.plan_classification_organize(results, config.organized_archive)
            all_operations.extend(ops)
            logger.info(f"파일 분류 계획: {len(ops)}개 작업")

        # 작업 실행
        if all_operations:
            print_section("작업 실행")

            if config.dry_run:
                print("\n🔍 드라이 런 모드 - 미리보기")
                report = mover.get_dry_run_report(all_operations)
                print(report)
            else:
                confirm = prompt_user(
                    f"\n{len(all_operations)}개 파일을 처리하시겠습니까?",
                    choices=["y", "n"],
                    default="n"
                ) if args.interactive else "y"

                if confirm.lower() == "y":
                    results = mover.execute_operations(all_operations, dry_run=False)
                    report = mover.get_execution_report(results)
                    print(report)
                    logger.log_summary(results)
                else:
                    print("  작업이 취소되었습니다.")

        else:
            print("\n✅ 처리할 작업이 없습니다.")

    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        logger.error("예상치 못한 오류", error=str(e))
        raise

    finally:
        # 로그 저장
        logger.finalize()
        log_paths = logger.get_log_paths()
        print(f"\n📝 로그 저장 위치:")
        print(f"   텍스트: {log_paths['text_log']}")
        print(f"   JSON: {log_paths['json_log']}")


def main():
    """엔트리 포인트"""
    run_cli()


if __name__ == "__main__":
    main()
