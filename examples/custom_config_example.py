#!/usr/bin/env python3
"""
사용자 맞춤 설정 예제

이 파일을 복사하여 본인의 환경에 맞게 수정하세요.
"""

import sys
from pathlib import Path

# 상위 디렉토리 모듈 import
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.main_cli import run_organizer, create_config

# ============================================================
# 사용자 맞춤 설정 - 아래 값들을 본인의 환경에 맞게 수정하세요
# ============================================================

# 정리 대상 폴더
TARGET_DIR = Path.home() / "Downloads"

# 정리된 파일 저장 위치
ARCHIVE_DIR = Path.home() / "_OrganizedFiles"

# 제외할 폴더 (정확한 이름 매칭)
EXCLUDED_FOLDERS = {
    # 기본 제외 폴더
    '.git', '.svn', '__pycache__', 'node_modules',
    '.venv', 'venv', '.idea', '.vscode',
    '_OrganizedFiles', '$RECYCLE.BIN', 'System Volume Information',
    'file_organizer',

    # 사용자 추가 폴더 - 여기에 제외할 폴더 추가
    # 'my_project',
    # '중요_데이터',
}

# 주제별 분류 대상 확장자
CLASSIFY_EXTENSIONS = {
    # 문서 파일
    '.pdf', '.doc', '.docx', '.hwp', '.hwpx',
    '.xls', '.xlsx', '.xlsm', '.csv',
    '.ppt', '.pptx',
    '.odt', '.ods', '.odp', '.rtf',
    '.txt', '.md',

    # 이미지 파일
    '.jpg', '.jpeg', '.png', '.gif', '.bmp',
    '.svg', '.webp', '.tiff', '.tif',

    # 압축 파일
    '.zip', '.rar', '.7z', '.tar', '.gz',
}


def main():
    """실행"""
    print("=" * 60)
    print("  맞춤 설정 파일 정리")
    print("=" * 60)
    print(f"\n대상 폴더: {TARGET_DIR}")
    print(f"저장 폴더: {ARCHIVE_DIR}")
    print(f"제외 폴더: {len(EXCLUDED_FOLDERS)}개")

    # 설정 생성
    config = create_config(
        target_dir=TARGET_DIR,
        excluded_folders=EXCLUDED_FOLDERS,
        archive_base=ARCHIVE_DIR,
        dry_run=True  # 먼저 미리보기로 실행
    )

    # 실행 (미리보기)
    run_organizer(
        config,
        classify_extensions=CLASSIFY_EXTENSIONS,
        execute=False,  # True로 변경하면 실제 실행
        include_year=True,
        include_month=False
    )

    print("\n" + "=" * 60)
    print("이것은 미리보기입니다.")
    print("실제 실행하려면 execute=False를 execute=True로 변경하세요.")
    print("=" * 60)


if __name__ == "__main__":
    main()
