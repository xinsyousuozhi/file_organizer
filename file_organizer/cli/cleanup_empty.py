#!/usr/bin/env python3
"""
빈 폴더 정리 모듈

파일 정리/이동 후 남은 빈 폴더들을 정리합니다.
"""

import sys
import argparse
from pathlib import Path
from typing import List, Set, Optional, Tuple


# 기본 제외 폴더 (삭제하면 안 되는 시스템/중요 폴더)
DEFAULT_EXCLUDE = {
    '.git', '.svn', '.hg',
    '.venv', 'venv', 'env',
    '__pycache__', 'node_modules',
    '.idea', '.vscode',
    '$RECYCLE.BIN', 'System Volume Information',
    '.cache', '.npm', '.yarn',
    'file_organizer',  # 이 도구 자체
    '_OrganizedFiles',
    # 사용자 프로젝트 폴더
    'head-repo', '2025구축', 'data_OC-main', 'data_PC-main',
}

# 시스템 파일 (이것만 있으면 빈 폴더로 취급)
SYSTEM_FILES = {
    '.DS_Store',
    'Thumbs.db',
    'desktop.ini',
    '.gitkeep',
    '.gitignore',
}


def is_effectively_empty(folder: Path, ignore_system_files: bool = True) -> bool:
    """
    폴더가 실질적으로 비어있는지 확인

    Args:
        folder: 확인할 폴더
        ignore_system_files: True면 시스템 파일만 있어도 비어있다고 판단

    Returns:
        비어있으면 True
    """
    try:
        contents = list(folder.iterdir())

        if not contents:
            return True

        if ignore_system_files:
            # 시스템 파일만 있는지 확인
            non_system = [
                item for item in contents
                if item.name not in SYSTEM_FILES
            ]
            return len(non_system) == 0

        return False
    except PermissionError:
        return False


def find_empty_folders(
    target_dir: Path,
    exclude: Optional[Set[str]] = None,
    ignore_system_files: bool = True,
    recursive: bool = True
) -> List[Path]:
    """
    빈 폴더 찾기

    Args:
        target_dir: 대상 폴더
        exclude: 제외할 폴더 이름들
        ignore_system_files: 시스템 파일만 있어도 비어있다고 판단
        recursive: 하위 폴더까지 재귀적으로 검색

    Returns:
        빈 폴더 경로 리스트 (깊은 폴더부터)
    """
    if exclude is None:
        exclude = DEFAULT_EXCLUDE.copy()

    empty_folders = []

    def scan_folder(folder: Path, depth: int = 0):
        """재귀적으로 폴더 스캔"""
        try:
            for item in folder.iterdir():
                try:
                    if not item.is_dir():
                        continue
                except (PermissionError, OSError):
                    continue

                # 제외 폴더 확인
                if item.name in exclude:
                    continue

                # 하위 폴더 먼저 처리 (재귀)
                if recursive:
                    scan_folder(item, depth + 1)

                # 빈 폴더 확인
                if is_effectively_empty(item, ignore_system_files):
                    empty_folders.append((item, depth))

        except (PermissionError, OSError):
            pass

    scan_folder(target_dir)

    # 깊은 폴더부터 정렬 (삭제 시 상위 폴더도 빈 폴더가 될 수 있음)
    empty_folders.sort(key=lambda x: (-x[1], str(x[0])))

    return [f[0] for f in empty_folders]


def cleanup_empty_folders(
    target_dir: Path,
    exclude: Optional[Set[str]] = None,
    ignore_system_files: bool = True,
    recursive: bool = True,
    dry_run: bool = True
) -> Tuple[int, int, List[str]]:
    """
    빈 폴더 정리 실행

    Args:
        target_dir: 대상 폴더
        exclude: 제외할 폴더 이름들
        ignore_system_files: 시스템 파일만 있어도 비어있다고 판단
        recursive: 하위 폴더까지 재귀적으로 검색
        dry_run: True면 미리보기만

    Returns:
        (성공 수, 실패 수, 오류 목록) 튜플
    """
    print("=" * 60)
    print("  빈 폴더 정리")
    print("=" * 60)
    print(f"\n대상 폴더: {target_dir}")
    print(f"드라이 런: {'예 (미리보기)' if dry_run else '아니오 (실제 삭제)'}")
    print(f"시스템 파일 무시: {'예' if ignore_system_files else '아니오'}")

    # 빈 폴더 찾기
    print("\n빈 폴더 검색 중...")
    empty_folders = find_empty_folders(
        target_dir, exclude, ignore_system_files, recursive
    )

    if not empty_folders:
        print("빈 폴더가 없습니다.")
        return 0, 0, []

    print(f"\n발견된 빈 폴더: {len(empty_folders)}개")

    # 미리보기
    print("\n삭제 대상 폴더:")
    for folder in empty_folders[:20]:
        rel_path = folder.relative_to(target_dir) if folder.is_relative_to(target_dir) else folder
        print(f"  - {rel_path}")

    if len(empty_folders) > 20:
        print(f"  ... 외 {len(empty_folders) - 20}개")

    if dry_run:
        print(f"\n[드라이 런] 실제 삭제하지 않았습니다.")
        return len(empty_folders), 0, []

    # 실제 삭제
    print("\n삭제 중...")
    success = 0
    failed = 0
    errors = []

    for folder in empty_folders:
        try:
            # 시스템 파일 먼저 삭제
            for item in folder.iterdir():
                if item.name in SYSTEM_FILES:
                    item.unlink()

            # 폴더 삭제
            folder.rmdir()
            success += 1

        except Exception as e:
            failed += 1
            errors.append(f"{folder}: {e}")

    print(f"\n완료: 삭제 {success}개, 실패 {failed}개")

    if errors:
        print("\n오류 목록:")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... 외 {len(errors) - 10}개")

    return success, failed, errors


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="빈 폴더 정리 도구 - 파일 이동 후 남은 빈 폴더 삭제"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=str(Path.home() / "Downloads"),
        help="대상 폴더 (기본: ~/Downloads)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="실제 삭제 실행 (기본은 드라이 런)"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="+",
        default=[],
        help="추가로 제외할 폴더들"
    )
    parser.add_argument(
        "--include-system-files",
        action="store_true",
        help="시스템 파일(.DS_Store 등)이 있으면 비어있지 않다고 판단"
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="하위 폴더 검색 안 함"
    )

    args = parser.parse_args()

    target_dir = Path(args.target)
    if not target_dir.exists():
        print(f"오류: 대상 폴더가 존재하지 않습니다: {target_dir}")
        sys.exit(1)

    # 제외 폴더 설정
    exclude = DEFAULT_EXCLUDE.copy()
    exclude.update(args.exclude)

    # 실행 확인
    if args.execute:
        confirm = input("\n빈 폴더를 실제로 삭제하시겠습니까? (yes 입력): ").strip()
        if confirm.lower() != "yes":
            print("취소되었습니다.")
            return

    success, failed, errors = cleanup_empty_folders(
        target_dir=target_dir,
        exclude=exclude,
        ignore_system_files=not args.include_system_files,
        recursive=not args.no_recursive,
        dry_run=not args.execute
    )

    if not args.execute and success > 0:
        print("\n" + "=" * 60)
        print("이것은 미리보기입니다.")
        print("실제 삭제하려면: python -m cli.cleanup_empty --execute")
        print("=" * 60)


if __name__ == "__main__":
    main()
