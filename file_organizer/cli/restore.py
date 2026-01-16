#!/usr/bin/env python3
"""
파일 복원 모듈

file_organizer가 이동한 파일들을 원래 위치로 되돌립니다.
로그 파일에서 이동 기록을 읽어 역방향으로 파일을 이동합니다.
"""

import sys
import json
import re
import shutil
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Optional


def parse_log_file(log_path: Path) -> List[Tuple[str, str]]:
    """
    JSON 로그 파일에서 이동 기록 파싱

    Returns:
        [(원본경로, 현재경로), ...] 리스트
    """
    moves = []

    print(f"로그 파일 읽는 중: {log_path}")

    with open(log_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"총 {data['total_entries']:,}개 로그 항목")

    for entry in data['entries']:
        action = entry.get('action', '')

        # "이동 완료: 원본 -> 대상" 형식 파싱
        if '이동 완료:' in action:
            match = re.search(r'이동 완료: (.+) -> (.+)', action)
            if match:
                source = match.group(1).strip()
                destination = match.group(2).strip()
                moves.append((source, destination))

    print(f"파싱된 이동 기록: {len(moves):,}개")
    return moves


def restore_files(
    moves: List[Tuple[str, str]],
    dry_run: bool = True
) -> Dict:
    """
    파일 복원 실행

    Args:
        moves: [(원본경로, 현재경로), ...] 리스트
        dry_run: True면 미리보기만

    Returns:
        결과 통계
    """
    results = {
        'total': len(moves),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'errors': []
    }

    print(f"\n{'='*60}")
    print(f"{'[DRY RUN] ' if dry_run else ''}파일 복원 시작")
    print(f"{'='*60}")
    print(f"복원할 파일: {len(moves):,}개\n")

    for i, (original_path, current_path) in enumerate(moves):
        original = Path(original_path)
        current = Path(current_path)

        # 진행 상황 표시
        if (i + 1) % 500 == 0:
            print(f"진행: {i + 1:,}/{len(moves):,} ({(i+1)/len(moves)*100:.1f}%)")

        # 현재 위치에 파일이 있는지 확인
        if not current.exists():
            results['skipped'] += 1
            continue

        # 원본 위치에 이미 파일이 있는지 확인
        if original.exists():
            results['skipped'] += 1
            continue

        if dry_run:
            results['success'] += 1
        else:
            try:
                # 원본 디렉토리 생성
                original.parent.mkdir(parents=True, exist_ok=True)

                # 파일 이동 (현재 -> 원본)
                shutil.move(str(current), str(original))
                results['success'] += 1

            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'current': str(current),
                    'original': str(original),
                    'error': str(e)
                })

    return results


def print_results(results: Dict, dry_run: bool):
    """결과 출력"""
    print(f"\n{'='*60}")
    print(f"{'[DRY RUN] ' if dry_run else ''}복원 결과")
    print(f"{'='*60}")
    print(f"총 대상: {results['total']:,}개")
    print(f"성공: {results['success']:,}개")
    print(f"실패: {results['failed']:,}개")
    print(f"건너뜀: {results['skipped']:,}개 (파일 없음 또는 이미 존재)")

    if results['errors']:
        print(f"\n오류 목록 (처음 10개):")
        for err in results['errors'][:10]:
            print(f"  - {err['current']}")
            print(f"    오류: {err['error']}")

    if dry_run:
        print(f"\n이것은 미리보기입니다. 실제 복원하려면:")
        print(f"  python -m cli.restore --execute")


def find_log_files(log_dir: Optional[Path] = None) -> List[Path]:
    """로그 파일 목록 조회"""
    if log_dir is None:
        log_dir = Path.home() / "_OrganizedFiles" / "logs"

    if not log_dir.exists():
        return []

    return sorted(log_dir.glob("organizer_*.json"), reverse=True)


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="파일 복원 도구 - 이동된 파일을 원래 위치로 되돌림"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="실제 복원 실행 (기본은 드라이 런)"
    )
    parser.add_argument(
        "--log",
        type=str,
        default=None,
        help="복원에 사용할 로그 파일 경로"
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="로그 폴더 경로 (기본: ~/_OrganizedFiles/logs)"
    )

    args = parser.parse_args()

    print("")
    print("=" * 60)
    print("  File Restore Tool - 파일 복원 도구")
    print("=" * 60)
    print("")

    # 로그 파일 찾기
    if args.log:
        selected_log = Path(args.log)
        if not selected_log.exists():
            print(f"오류: 로그 파일을 찾을 수 없습니다: {selected_log}")
            sys.exit(1)
    else:
        log_dir = Path(args.log_dir) if args.log_dir else None
        json_logs = find_log_files(log_dir)

        if not json_logs:
            print("오류: 로그 파일을 찾을 수 없습니다.")
            sys.exit(1)

        print("사용 가능한 로그 파일:")
        for i, log in enumerate(json_logs[:5]):
            size_mb = log.stat().st_size / (1024 * 1024)
            print(f"  {i + 1}. {log.name} ({size_mb:.1f} MB)")

        try:
            choice = input("\n복원할 로그 번호 선택 (기본: 1, 가장 최근): ").strip()
            log_choice = int(choice) - 1 if choice else 0
        except ValueError:
            log_choice = 0

        if log_choice < 0 or log_choice >= len(json_logs):
            log_choice = 0

        selected_log = json_logs[log_choice]

    print(f"\n선택된 로그: {selected_log.name}")

    # 로그 파싱
    moves = parse_log_file(selected_log)

    if not moves:
        print("이동 기록이 없습니다.")
        sys.exit(0)

    # 복원 확인
    dry_run = not args.execute

    if dry_run:
        print("\n[DRY RUN 모드] 실제 파일은 이동되지 않습니다.")
        confirm = input("미리보기를 진행하시겠습니까? (y/n): ").strip().lower()
    else:
        print("\n주의: 실제 복원 모드입니다!")
        confirm = input(f"{len(moves):,}개 파일을 원래 위치로 복원하시겠습니까? (yes를 입력): ").strip().lower()
        if confirm != "yes":
            confirm = "n"
        else:
            confirm = "y"

    if confirm != 'y':
        print("취소되었습니다.")
        sys.exit(0)

    results = restore_files(moves, dry_run=dry_run)
    print_results(results, dry_run)


if __name__ == "__main__":
    main()
