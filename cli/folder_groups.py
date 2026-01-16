#!/usr/bin/env python3
"""
폴더 그룹화 모듈

대상 폴더 내 하위 폴더들을 카테고리별로 그룹화합니다.
"""

import sys
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


# 기본 제외 폴더
DEFAULT_EXCLUDE = {
    'file_organizer',
    '_OrganizedFiles',
    '.git', '.svn', '__pycache__',
    '$RECYCLE.BIN', 'System Volume Information',
}


def organize_folders(
    target_dir: Path,
    groups: Dict[str, List[str]],
    exclude: Optional[Set[str]] = None,
    dry_run: bool = True
) -> Tuple[int, int]:
    """
    폴더 그룹화 실행

    Args:
        target_dir: 대상 폴더
        groups: {그룹명: [폴더명, ...]} 딕셔너리
        exclude: 제외할 폴더 이름들
        dry_run: True면 미리보기만

    Returns:
        (성공 수, 실패 수) 튜플
    """
    if exclude is None:
        exclude = DEFAULT_EXCLUDE.copy()

    # 그룹 폴더 이름도 제외 목록에 추가
    exclude.update(groups.keys())

    print("=" * 60)
    print("  폴더 그룹화")
    print("=" * 60)
    print(f"\n대상 폴더: {target_dir}")
    print(f"드라이 런: {'예 (미리보기)' if dry_run else '아니오 (실제 실행)'}")
    print(f"제외 폴더: {len(exclude)}개")

    moves = []

    for group_name, folders in groups.items():
        group_path = target_dir / group_name

        print(f"\n[{group_name}]")

        for folder_name in folders:
            source = target_dir / folder_name
            dest = group_path / folder_name

            if not source.exists():
                print(f"  (없음) {folder_name}")
                continue

            if source.name in exclude:
                print(f"  (제외) {folder_name}")
                continue

            moves.append((source, dest, group_name))
            print(f"  -> {folder_name}")

    print(f"\n총 {len(moves)}개 폴더 이동 예정")

    if dry_run:
        print("\n[드라이 런] 실제 이동하지 않았습니다.")
        return len(moves), 0

    # 실제 이동
    print("\n이동 중...")
    success = 0
    failed = 0

    for source, dest, group_name in moves:
        try:
            # 그룹 폴더 생성
            dest.parent.mkdir(parents=True, exist_ok=True)

            # 폴더 이동
            shutil.move(str(source), str(dest))
            print(f"  OK: {source.name} -> {group_name}/")
            success += 1

        except Exception as e:
            print(f"  FAIL: {source.name} - {e}")
            failed += 1

    print(f"\n완료: 성공 {success}개, 실패 {failed}개")
    return success, failed


def scan_folders(target_dir: Path, exclude: Optional[Set[str]] = None) -> List[str]:
    """
    대상 폴더의 하위 폴더 목록 조회

    Args:
        target_dir: 대상 폴더
        exclude: 제외할 폴더 이름들

    Returns:
        폴더 이름 리스트
    """
    if exclude is None:
        exclude = DEFAULT_EXCLUDE

    folders = []
    for item in target_dir.iterdir():
        if item.is_dir() and item.name not in exclude:
            folders.append(item.name)

    return sorted(folders)


def interactive_grouping(target_dir: Path) -> Dict[str, List[str]]:
    """
    대화형 폴더 그룹 설정

    Args:
        target_dir: 대상 폴더

    Returns:
        {그룹명: [폴더명, ...]} 딕셔너리
    """
    folders = scan_folders(target_dir)

    print(f"\n{target_dir}의 하위 폴더 ({len(folders)}개):")
    for i, name in enumerate(folders, 1):
        print(f"  {i:2}. {name}")

    groups = {}

    print("\n그룹 설정 (빈 줄 입력 시 종료)")
    print("형식: 그룹명 폴더번호1,폴더번호2,...")
    print("예: _데이터 1,3,5")

    while True:
        try:
            line = input("\n그룹 입력: ").strip()
            if not line:
                break

            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                print("형식 오류. 예: _데이터 1,3,5")
                continue

            group_name = parts[0]
            indices = [int(x.strip()) for x in parts[1].split(',')]

            selected = [folders[i-1] for i in indices if 0 < i <= len(folders)]

            if selected:
                groups[group_name] = selected
                print(f"  {group_name}: {', '.join(selected)}")

        except (ValueError, IndexError) as e:
            print(f"입력 오류: {e}")

    return groups


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="폴더 그룹화 도구 - 하위 폴더들을 카테고리별로 정리"
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
        help="실제 이동 실행 (기본은 드라이 런)"
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="대화형 그룹 설정"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="+",
        default=[],
        help="추가로 제외할 폴더들"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="그룹 설정 JSON 파일"
    )

    args = parser.parse_args()

    target_dir = Path(args.target)
    if not target_dir.exists():
        print(f"오류: 대상 폴더가 존재하지 않습니다: {target_dir}")
        sys.exit(1)

    # 제외 폴더 설정
    exclude = DEFAULT_EXCLUDE.copy()
    exclude.update(args.exclude)

    # 그룹 설정 로드
    if args.config:
        import json
        with open(args.config, 'r', encoding='utf-8') as f:
            groups = json.load(f)
    elif args.interactive:
        groups = interactive_grouping(target_dir)
        if not groups:
            print("그룹 설정이 없습니다.")
            return
    else:
        print("오류: --config 또는 --interactive 옵션이 필요합니다.")
        print("\n사용 예:")
        print("  대화형: python -m cli.folder_groups --interactive")
        print("  설정파일: python -m cli.folder_groups --config groups.json")
        sys.exit(1)

    # 실행 확인
    if args.execute:
        confirm = input("\n폴더를 실제로 이동하시겠습니까? (yes 입력): ").strip()
        if confirm.lower() != "yes":
            print("취소되었습니다.")
            return

    organize_folders(
        target_dir=target_dir,
        groups=groups,
        exclude=exclude,
        dry_run=not args.execute
    )

    if not args.execute:
        print("\n" + "=" * 60)
        print("이것은 미리보기입니다.")
        print("실제 실행하려면: python -m cli.folder_groups --execute [옵션]")
        print("=" * 60)


if __name__ == "__main__":
    main()
