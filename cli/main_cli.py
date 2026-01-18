#!/usr/bin/env python3
"""
파일 정리 CLI - 메인 실행 모듈

기능:
1. 중복 파일 처리 (SHA256 해싱)
2. 버전 파일 그룹화
3. 문서/이미지 파일 주제별 분류
"""

import sys
import argparse
from pathlib import Path
from typing import Set, Optional

# 상위 모듈 import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import OrganizerConfig
from src.organizer import FileOrganizer


# ============================================================
# 기본 설정값 (필요시 수정)
# ============================================================

DEFAULT_EXCLUDED_FOLDERS = {
    # 시스템/개발 폴더
    '.git', '.svn', '__pycache__', 'node_modules',
    '.venv', 'venv', '.idea', '.vscode',
    '_OrganizedFiles', '$RECYCLE.BIN', 'System Volume Information',
    '.cache', '.npm', '.yarn', 'dist', 'build', 'target',
    'file_organizer',  # 이 도구 자체
}

DEFAULT_CLASSIFY_EXTENSIONS = {
    # 문서 파일
    '.pdf', '.doc', '.docx', '.hwp', '.hwpx',
    '.xls', '.xlsx', '.xlsm', '.csv',
    '.ppt', '.pptx',
    '.odt', '.ods', '.odp', '.rtf',
    '.txt', '.md', '.rst',

    # 이미지 파일
    '.jpg', '.jpeg', '.png', '.gif', '.bmp',
    '.svg', '.webp', '.ico', '.tiff', '.tif',
    '.raw', '.psd', '.ai', '.eps',

    # 압축 파일
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
}


def create_config(
    target_dir: Path,
    excluded_folders: Optional[Set[str]] = None,
    archive_base: Optional[Path] = None,
    dry_run: bool = True
) -> OrganizerConfig:
    """
    사용자 맞춤 설정 생성

    Args:
        target_dir: 정리 대상 폴더
        excluded_folders: 제외할 폴더 이름들
        archive_base: 정리된 파일 저장 위치
        dry_run: 드라이 런 모드

    Returns:
        OrganizerConfig 인스턴스
    """
    if excluded_folders is None:
        excluded_folders = DEFAULT_EXCLUDED_FOLDERS

    if archive_base is None:
        archive_base = Path.home() / "_OrganizedFiles"

    config = OrganizerConfig(
        target_directories=[target_dir],
        archive_base=archive_base,
        dry_run=dry_run,
        use_recycle_bin=False,
    )

    # 제외 폴더 설정
    config.excluded_dirs = excluded_folders

    # 문서 확장자 확장
    config.document_extensions = {
        '.pdf', '.doc', '.docx', '.hwp', '.hwpx',
        '.xls', '.xlsx', '.xlsm', '.csv',
        '.ppt', '.pptx', '.odp',
        '.odt', '.ods', '.rtf',
        '.txt', '.md', '.rst', '.tex',
    }

    # 이미지 확장자 확장
    config.image_extensions = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp',
        '.svg', '.webp', '.ico', '.tiff', '.tif',
        '.raw', '.psd', '.ai', '.eps', '.heic',
    }

    return config


def run_organizer(
    config: OrganizerConfig,
    classify_extensions: Optional[Set[str]] = None,
    execute: bool = False,
    include_year: bool = True,
    include_month: bool = False
):
    """
    파일 정리 실행

    Args:
        config: OrganizerConfig 인스턴스
        classify_extensions: 분류 대상 확장자
        execute: True면 실제 실행, False면 드라이 런
        include_year: 연도 폴더 생성
        include_month: 월 폴더 생성 (연도 하위)
    """
    if classify_extensions is None:
        classify_extensions = DEFAULT_CLASSIFY_EXTENSIONS

    target_dir = config.target_directories[0]

    print("=" * 60)
    print("  파일 정리 도구")
    print("=" * 60)
    print(f"\n대상 폴더: {target_dir}")
    print(f"드라이 런: {'아니오 (실제 실행)' if execute else '예 (미리보기)'}")
    print(f"\n제외 폴더: {len(config.excluded_dirs)}개")
    print(f"분류 대상 확장자: {len(classify_extensions)}개")

    config.dry_run = not execute
    organizer = FileOrganizer(config)

    try:
        # 1. 파일 스캔
        print("\n" + "-" * 50)
        print("1단계: 파일 스캔")
        print("-" * 50)
        files = organizer.scan_directories()
        print(f"   스캔된 파일: {len(files):,}개")

        # 2. 중복 파일 탐지
        print("\n" + "-" * 50)
        print("2단계: 중복 파일 탐지")
        print("-" * 50)
        duplicates = organizer.find_duplicates()

        if duplicates:
            summary = organizer.duplicate_finder.get_summary(duplicates)
            print(f"   중복 그룹: {summary['duplicate_groups']}개")
            print(f"   중복 파일: {summary['total_duplicate_files']}개")
            print(f"   절약 가능: {summary['total_wasted_space_formatted']}")
        else:
            print("   중복 파일 없음")

        # 3. 버전 파일 탐지
        print("\n" + "-" * 50)
        print("3단계: 버전 파일 탐지")
        print("-" * 50)
        versions = organizer.find_version_groups()
        print(f"   버전 그룹: {len(versions)}개")

        # 4. 문서/이미지 파일 분류
        print("\n" + "-" * 50)
        print("4단계: 문서/이미지 파일 분류")
        print("-" * 50)

        # 분류 대상 파일만 필터링
        classify_files = [
            f for f in files
            if f.path.suffix.lower() in classify_extensions
        ]
        print(f"   분류 대상: {len(classify_files):,}개 (문서/이미지)")

        if classify_files:
            # 중복 파일 제외를 반영하기 위해 FileOrganizer의 메서드 사용
            classifications = organizer.classify_files(
                classify_files, by_content=True, by_date=True, exclude_duplicates=True, keep_strategy="newest"
            )

            # 대상 경로 생성
            for result in classifications:
                path_parts = [config.organized_archive, result.category]
                if include_year and result.year:
                    path_parts.append(str(result.year))
                if include_month and result.month:
                    path_parts.append(f"{result.month:02d}")
                target_dir = Path(*[str(p) for p in path_parts])
                result.target_path = target_dir / result.file_info.path.name

            summary = organizer.classifier.get_classification_summary(classifications)
            print(f"   카테고리별 분포:")
            for cat, count in sorted(summary['by_category'].items(),
                                     key=lambda x: -x[1])[:10]:
                print(f"      {cat}: {count}개")

            organizer._classifications = classifications

        # 5. 정리 계획 수립
        print("\n" + "-" * 50)
        print("5단계: 정리 계획 수립")
        print("-" * 50)

        operations = organizer.plan_cleanup(
            duplicates=True,
            versions=False,  # 버전은 보고서만
            organize=True if classify_files else False,
            keep_strategy="newest"
        )

        print(f"   계획된 작업: {len(operations):,}개")

        # 6. 실행
        if operations:
            print("\n" + "-" * 50)
            print("6단계: 실행" + (" (드라이 런)" if not execute else ""))
            print("-" * 50)

            if not execute:
                # 드라이 런 보고서
                report = organizer.get_dry_run_report()
                print(report)
            else:
                results = organizer.execute(dry_run=False)
                report = organizer.get_execution_report(results)
                print(report)
        else:
            print("\n처리할 작업이 없습니다.")

        # 버전 파일 보고서 (참고용)
        if versions:
            print("\n" + "=" * 60)
            print("참고: 버전 파일 그룹 (상위 5개)")
            print("=" * 60)
            for i, group in enumerate(versions[:5]):
                print(f"\n{i+1}. {group.base_name}{group.extension} ({group.count}개 버전)")
                for f in group.files[:3]:
                    print(f"   - {f.path.name}")
                if group.count > 3:
                    print(f"   ... 외 {group.count - 3}개")

        return operations

    finally:
        organizer.finalize()


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="파일 정리 도구 - 중복 제거, 버전 관리, 주제별 분류"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=str(Path.home() / "Downloads"),
        help="정리 대상 폴더 (기본: ~/Downloads)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="실제 파일 이동 실행 (기본은 드라이 런)"
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

    args = parser.parse_args()

    target_dir = Path(args.target)
    if not target_dir.exists():
        print(f"오류: 대상 폴더가 존재하지 않습니다: {target_dir}")
        sys.exit(1)

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

    if args.execute:
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
        include_month=args.with_month
    )

    if not args.execute:
        print("\n" + "=" * 60)
        print("이것은 미리보기입니다.")
        print("실제 실행하려면: python -m cli.main_cli --execute")
        print("=" * 60)


if __name__ == "__main__":
    main()
