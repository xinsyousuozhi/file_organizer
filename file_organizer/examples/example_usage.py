#!/usr/bin/env python3
"""
파일 정리 도구 사용 예제

이 스크립트는 FileOrganizer 클래스를 프로그래밍 방식으로 사용하는 방법을 보여줍니다.
"""

import sys
from pathlib import Path

# 상위 디렉토리의 src 모듈 import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import OrganizerConfig
from src.organizer import FileOrganizer, quick_scan
from src.duplicate_finder import DuplicateFinder
from src.version_manager import VersionManager, format_version_report
from src.classifier import FileClassifier, format_classification_report


def example_1_quick_duplicate_scan():
    """
    예제 1: 빠른 중복 파일 스캔

    지정된 폴더에서 중복 파일을 빠르게 찾아 결과를 출력합니다.
    """
    print("=" * 60)
    print("예제 1: 빠른 중복 파일 스캔")
    print("=" * 60)

    # 스캔할 디렉토리 (본인의 경로로 수정)
    target_dir = Path.home() / "Downloads"

    if not target_dir.exists():
        print(f"대상 디렉토리가 없습니다: {target_dir}")
        return

    # 빠른 스캔 실행
    results = quick_scan(target_dir, find_duplicates=True)

    print(f"\n스캔 디렉토리: {results['directory']}")
    print(f"스캔된 파일: {results['scanned_files']:,}개")

    if "duplicates" in results:
        dup = results["duplicates"]
        print(f"\n중복 그룹: {dup['duplicate_groups']}개")
        print(f"중복 파일: {dup['total_duplicate_files']}개")
        print(f"절약 가능 공간: {dup['total_wasted_space_formatted']}")


def example_2_full_analysis():
    """
    예제 2: 전체 분석 (중복 + 버전 + 분류)

    모든 분석 기능을 사용하여 폴더를 분석합니다.
    """
    print("\n" + "=" * 60)
    print("예제 2: 전체 분석")
    print("=" * 60)

    # 설정 생성
    config = OrganizerConfig(
        target_directories=[Path.home() / "Downloads"],
        archive_base=Path.home() / "_OrganizedFiles",
        dry_run=True,  # 드라이 런 모드 (실제 파일 변경 없음)
    )

    # FileOrganizer 초기화
    organizer = FileOrganizer(config)

    try:
        # 1. 파일 스캔
        print("\n1. 파일 스캔 중...")
        files = organizer.scan_directories()
        print(f"   스캔된 파일: {len(files):,}개")

        # 2. 중복 파일 탐지
        print("\n2. 중복 파일 탐지 중...")
        duplicates = organizer.find_duplicates()
        print(f"   중복 그룹: {len(duplicates)}개")

        # 3. 버전 그룹 탐지
        print("\n3. 버전 그룹 탐지 중...")
        versions = organizer.find_version_groups()
        print(f"   버전 그룹: {len(versions)}개")

        # 4. 파일 분류
        print("\n4. 파일 분류 중...")
        classifications = organizer.classify_files(by_content=True, by_date=True)
        summary = organizer.classifier.get_classification_summary(classifications)
        print(f"   분류된 파일: {len(classifications):,}개")
        print(f"   카테고리: {list(summary['by_category'].keys())}")

        # 5. 통계 출력
        print("\n5. 전체 통계:")
        stats = organizer.get_statistics()
        for key, value in stats.items():
            if not isinstance(value, dict):
                print(f"   {key}: {value}")

    finally:
        organizer.finalize()


def example_3_duplicate_cleanup_plan():
    """
    예제 3: 중복 파일 정리 계획 (드라이 런)

    중복 파일을 찾고 정리 계획을 세운 후 드라이 런 보고서를 출력합니다.
    """
    print("\n" + "=" * 60)
    print("예제 3: 중복 파일 정리 계획")
    print("=" * 60)

    config = OrganizerConfig(
        target_directories=[Path.home() / "Downloads"],
        dry_run=True,
    )

    organizer = FileOrganizer(config)

    try:
        # 스캔 및 중복 탐지
        organizer.scan_directories()
        duplicates = organizer.find_duplicates()

        if duplicates:
            # 정리 계획 수립
            operations = organizer.plan_cleanup(
                duplicates=True,
                keep_strategy="newest"  # 최신 파일 보존
            )

            # 드라이 런 보고서 출력
            report = organizer.get_dry_run_report()
            print(report)
        else:
            print("\n중복 파일이 없습니다.")

    finally:
        organizer.finalize()


def example_4_classification_report():
    """
    예제 4: 파일 분류 보고서

    파일을 분류하고 상세 보고서를 출력합니다.
    """
    print("\n" + "=" * 60)
    print("예제 4: 파일 분류 보고서")
    print("=" * 60)

    config = OrganizerConfig(
        target_directories=[Path.home() / "Downloads"],
    )

    organizer = FileOrganizer(config)

    try:
        # 스캔
        organizer.scan_directories()

        # 분류
        classifications = organizer.classify_files(by_content=True, by_date=True)

        # 보고서 출력
        summary = organizer.classifier.get_classification_summary(classifications)
        report = format_classification_report(summary)
        print(report)

    finally:
        organizer.finalize()


def example_5_custom_category():
    """
    예제 5: 사용자 정의 카테고리로 분류

    사용자가 정의한 카테고리 키워드를 사용하여 분류합니다.
    """
    print("\n" + "=" * 60)
    print("예제 5: 사용자 정의 카테고리")
    print("=" * 60)

    config = OrganizerConfig(
        target_directories=[Path.home() / "Downloads"],
    )

    organizer = FileOrganizer(config)

    try:
        # 사용자 정의 카테고리 추가
        organizer.classifier.add_category(
            "프로젝트_A",
            ["project_a", "프로젝트A", "client_a", "고객사A"]
        )
        organizer.classifier.add_category(
            "프로젝트_B",
            ["project_b", "프로젝트B", "client_b", "고객사B"]
        )

        # 스캔 및 분류
        organizer.scan_directories()
        classifications = organizer.classify_files()

        # 결과 요약
        summary = organizer.classifier.get_classification_summary(classifications)
        print("\n카테고리별 파일 수:")
        for cat, count in sorted(summary["by_category"].items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}개")

    finally:
        organizer.finalize()


def example_6_programmatic_execution():
    """
    예제 6: 프로그래밍 방식 실행

    코드에서 직접 파일 정리를 실행하는 방법을 보여줍니다.
    주의: dry_run=False로 설정하면 실제로 파일이 이동됩니다!
    """
    print("\n" + "=" * 60)
    print("예제 6: 프로그래밍 방식 실행 (드라이 런)")
    print("=" * 60)

    config = OrganizerConfig(
        target_directories=[Path.home() / "Downloads"],
        archive_base=Path.home() / "_OrganizedFiles",
        dry_run=True,  # 안전을 위해 드라이 런 모드
        use_recycle_bin=False,  # 아카이브 폴더로 이동
    )

    organizer = FileOrganizer(config)

    try:
        # 전체 파이프라인 실행
        print("\n1. 스캔 중...")
        organizer.scan_directories()

        print("2. 분석 중...")
        organizer.find_duplicates()
        organizer.classify_files()

        print("3. 정리 계획 수립 중...")
        operations = organizer.plan_cleanup(
            duplicates=True,
            organize=True,
        )
        print(f"   계획된 작업: {len(operations)}개")

        print("4. 실행 중 (드라이 런)...")
        results = organizer.execute(dry_run=True)

        print(f"\n결과:")
        print(f"  총 작업: {results['total']}개")
        print(f"  성공: {results['success']}개")
        print(f"  실패: {results['failed']}개")

        # 실제 실행하려면:
        # results = organizer.execute(dry_run=False)

    finally:
        organizer.finalize()


def main():
    """메인 함수: 모든 예제 실행"""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║               파일 정리 도구 - 사용 예제 모음                             ║
╚══════════════════════════════════════════════════════════════════════╝

이 스크립트는 FileOrganizer를 프로그래밍 방식으로 사용하는
다양한 예제를 제공합니다.

주의: 기본적으로 모든 예제는 드라이 런 모드로 실행됩니다.
      실제 파일 변경은 발생하지 않습니다.

실행할 예제를 선택하세요:
  1. 빠른 중복 파일 스캔
  2. 전체 분석 (중복 + 버전 + 분류)
  3. 중복 파일 정리 계획
  4. 파일 분류 보고서
  5. 사용자 정의 카테고리
  6. 프로그래밍 방식 실행
  a. 모든 예제 실행
  q. 종료
""")

    choice = input("선택 (1-6, a, q): ").strip().lower()

    examples = {
        "1": example_1_quick_duplicate_scan,
        "2": example_2_full_analysis,
        "3": example_3_duplicate_cleanup_plan,
        "4": example_4_classification_report,
        "5": example_5_custom_category,
        "6": example_6_programmatic_execution,
    }

    if choice == "q":
        print("종료합니다.")
        return

    if choice == "a":
        for func in examples.values():
            try:
                func()
            except Exception as e:
                print(f"오류 발생: {e}")
            print("\n")
    elif choice in examples:
        try:
            examples[choice]()
        except Exception as e:
            print(f"오류 발생: {e}")
    else:
        print("잘못된 선택입니다.")


if __name__ == "__main__":
    main()
