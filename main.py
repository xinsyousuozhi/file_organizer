#!/usr/bin/env python3
"""
파일 정리 도구 - 메인 진입점

사용법:
    # CLI 모드 (기본)
    python main.py [대상폴더] [--execute] [옵션]

    # GUI 모드
    python main.py --gui

    # 복원
    python main.py --restore [--execute]

    # 빈 폴더 정리
    python main.py --cleanup-empty [대상폴더] [--execute]

기능:
    1. 중복 파일 처리 (SHA256 해싱)
    2. 버전 파일 그룹화
    3. 문서/이미지 주제별 분류
    4. 빈 폴더 정리
    5. 파일 복원
"""

import sys
import io
import argparse
from pathlib import Path

# Windows 콘솔 인코딩 설정 (CLI 환경에서만)
def _setup_console_encoding(is_gui=False):
    """
    Windows 콘솔 인코딩 설정

    Args:
        is_gui: GUI 모드 여부 (True면 인코딩 설정 스킵)
    """
    if is_gui:
        return  # GUI는 인코딩 설정 불필요

    if sys.platform == 'win32':
        try:
            if hasattr(sys.stdout, 'buffer') and sys.stdout.buffer and not sys.stdout.closed:
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            if hasattr(sys.stderr, 'buffer') and sys.stderr.buffer and not sys.stderr.closed:
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except (ValueError, AttributeError, OSError):
            pass


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="파일 정리 도구 - 중복 제거, 버전 관리, 주제별 분류",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
    # 미리보기 (드라이 런)
    python main.py ~/Downloads

    # 실제 실행
    python main.py ~/Downloads --execute

    # GUI 실행
    python main.py --gui

    # 복원
    python main.py --restore

    # 빈 폴더 정리
    python main.py --cleanup-empty ~/Downloads --execute
        """
    )

    # 모드 선택
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--gui",
        action="store_true",
        help="GUI 모드로 실행"
    )
    mode_group.add_argument(
        "--restore",
        action="store_true",
        help="복원 모드 실행"
    )
    mode_group.add_argument(
        "--cleanup-empty",
        action="store_true",
        help="빈 폴더 정리 모드"
    )
    mode_group.add_argument(
        "--folder-groups",
        action="store_true",
        help="폴더 그룹화 모드 (대화형)"
    )

    # 공통 옵션
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="정리 대상 폴더 (기본: ~/Downloads)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="실제 실행 (기본은 드라이 런)"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="확인 없이 실행"
    )
    parser.add_argument(
        "--archive",
        type=str,
        default=None,
        help="정리된 파일 저장 위치 (기본: ~/_OrganizedFiles)"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="+",
        default=[],
        help="추가로 제외할 폴더들"
    )
    parser.add_argument(
        "--with-month",
        action="store_true",
        help="월별 하위 폴더 생성 (기본: 연도까지만)"
    )
    parser.add_argument(
        "--llm",
        type=str,
        default=None,
        choices=["gemini-cli", "gemini", "claude", "openai", "ollama"],
        help="LLM 분류 사용 (gemini-cli 권장)"
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default=None,
        help="LLM 모델 이름 (예: gemini-2.5-flash)"
    )

    args = parser.parse_args()

    # GUI 모드 체크 (인코딩 설정 전에)
    is_gui = args.gui if hasattr(args, 'gui') else False

    # 인코딩 설정 (GUI가 아닐 때만)
    _setup_console_encoding(is_gui=is_gui)

    # 기본 대상 폴더
    if args.target is None:
        args.target = str(Path.home() / "Downloads")

    target_dir = Path(args.target)

    # GUI 모드
    if args.gui:
        try:
            from gui.main_gui import run_gui
            run_gui()
        except ImportError as e:
            print(f"오류: GUI 모듈을 불러올 수 없습니다: {e}")
            print("tkinter가 설치되어 있는지 확인하세요.")
            sys.exit(1)
        return

    # 복원 모드
    if args.restore:
        from cli.restore import main as restore_main
        sys.argv = ['restore']
        if args.execute:
            sys.argv.append('--execute')
        restore_main()
        return

    # 빈 폴더 정리 모드
    if args.cleanup_empty:
        from cli.cleanup_empty import main as cleanup_main
        sys.argv = ['cleanup_empty', str(target_dir)]
        if args.execute:
            sys.argv.append('--execute')
        if args.yes:
            sys.argv.append('-y')
        if args.exclude:
            sys.argv.extend(['--exclude'] + args.exclude)
        cleanup_main()
        return

    # 폴더 그룹화 모드
    if args.folder_groups:
        from cli.folder_groups import main as folder_main
        sys.argv = ['folder_groups', str(target_dir), '--interactive']
        if args.execute:
            sys.argv.append('--execute')
        folder_main()
        return

    # CLI 정리 모드 (기본)
    if not target_dir.exists():
        print(f"오류: 대상 폴더가 존재하지 않습니다: {target_dir}")
        sys.exit(1)

    from cli.main_cli import run_organizer, create_config, DEFAULT_EXCLUDED_FOLDERS

    # 제외 폴더 설정
    excluded = DEFAULT_EXCLUDED_FOLDERS.copy()
    excluded.update(args.exclude)

    # 아카이브 경로
    archive_base = Path(args.archive) if args.archive else None

    config = create_config(
        target_dir=target_dir,
        excluded_folders=excluded,
        archive_base=archive_base,
        dry_run=True
    )

    if args.execute and not args.yes:
        print("\n" + "!" * 60)
        print("  주의: 실제 실행 모드입니다!")
        print("!" * 60)
        confirm = input("\n계속하시겠습니까? (yes 입력): ").strip()
        if confirm.lower() != "yes":
            print("취소되었습니다.")
            return

    run_organizer(
        config,
        execute=args.execute,
        include_year=True,
        include_month=args.with_month,
        llm_provider=args.llm,
        llm_model=args.llm_model
    )

    if not args.execute:
        print("\n" + "=" * 60)
        print("이것은 미리보기입니다.")
        print("실제 실행하려면: python main.py --execute")
        print("=" * 60)


if __name__ == "__main__":
    main()
