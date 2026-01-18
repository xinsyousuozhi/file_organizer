"""
YAML 설정 파일 로더
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from .config import OrganizerConfig
from .llm_classifier import LLMConfig


def load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """
    YAML 설정 파일 로드

    Args:
        config_path: YAML 파일 경로

    Returns:
        설정 딕셔너리
    """
    if not config_path.exists():
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)

    return config_data or {}


def expand_path(path_str: str) -> Path:
    """경로 확장 (~/ 처리)"""
    return Path(path_str).expanduser().resolve()


def create_config_from_yaml(yaml_path: Path) -> OrganizerConfig:
    """
    YAML 파일에서 OrganizerConfig 생성

    Args:
        yaml_path: YAML 설정 파일 경로

    Returns:
        OrganizerConfig 인스턴스
    """
    data = load_yaml_config(yaml_path)

    # 대상 디렉토리
    target_dirs = [
        expand_path(d) for d in data.get('target_directories', [])
    ]
    if not target_dirs:
        target_dirs = [Path.home() / "Downloads"]

    # 아카이브 경로
    archive_base = expand_path(
        data.get('archive_base', '~/_OrganizedFiles')
    )

    # 설정 생성
    config = OrganizerConfig(
        target_directories=target_dirs,
        archive_base=archive_base,
        dry_run=data.get('dry_run', True),
        use_recycle_bin=data.get('use_recycle_bin', False),
    )

    # 제외 폴더
    if 'excluded_folders' in data:
        config.excluded_dirs = set(data['excluded_folders'])

    # 제외 패턴
    if 'excluded_patterns' in data:
        config.excluded_patterns = set(data['excluded_patterns'])

    # LLM 설정
    if 'llm' in data:
        llm_data = data['llm']
        if llm_data.get('max_file_size'):
            config.llm_max_file_size = llm_data['max_file_size']
        if llm_data.get('content_preview_length'):
            config.llm_content_preview_length = llm_data['content_preview_length']
        if llm_data.get('batch_size_limit'):
            config.llm_batch_size_limit = llm_data['batch_size_limit']

    return config


def create_llm_config_from_yaml(yaml_path: Path) -> Optional[LLMConfig]:
    """
    YAML 파일에서 LLMConfig 생성

    Args:
        yaml_path: YAML 설정 파일 경로

    Returns:
        LLMConfig 인스턴스 또는 None
    """
    data = load_yaml_config(yaml_path)

    if 'llm' not in data:
        return None

    llm_data = data['llm']

    if not llm_data.get('enabled', False):
        return None

    provider = llm_data.get('provider', 'none')
    if provider == 'none':
        return None

    return LLMConfig(
        provider=provider,
        api_key=llm_data.get('api_key'),
        model=llm_data.get('model'),
        base_url=llm_data.get('base_url'),
        max_tokens=llm_data.get('max_tokens', 500),
        temperature=llm_data.get('temperature', 0.3),
    )


def get_classification_options(yaml_path: Path) -> Dict[str, Any]:
    """
    YAML에서 분류 옵션 추출

    Returns:
        분류 옵션 딕셔너리
    """
    data = load_yaml_config(yaml_path)

    classification = data.get('classification', {})

    return {
        'by_content': classification.get('by_content', True),
        'by_date': classification.get('by_date', True),
        'include_year': classification.get('include_year', True),
        'include_month': classification.get('include_month', False),
    }


def get_duplicate_options(yaml_path: Path) -> Dict[str, Any]:
    """
    YAML에서 중복 파일 옵션 추출

    Returns:
        중복 처리 옵션 딕셔너리
    """
    data = load_yaml_config(yaml_path)

    duplicates = data.get('duplicates', {})

    return {
        'enabled': duplicates.get('enabled', True),
        'keep_strategy': duplicates.get('keep_strategy', 'newest'),
    }


def get_paper_options(yaml_path: Path) -> Dict[str, Any]:
    """
    YAML에서 논문 처리 옵션 추출

    Returns:
        논문 처리 옵션 딕셔너리
    """
    data = load_yaml_config(yaml_path)

    papers = data.get('papers', {})

    return {
        'enabled': papers.get('enabled', False),
        'classify_by': papers.get('classify_by', 'topic'),  # topic or author
        'rename_files': papers.get('rename_files', False),
        'extract_metadata': papers.get('extract_metadata', True),
    }


def get_custom_categories(yaml_path: Path) -> Dict[str, list]:
    """
    YAML에서 사용자 정의 카테고리 추출

    Returns:
        카테고리 딕셔너리
    """
    data = load_yaml_config(yaml_path)
    return data.get('custom_categories', {})
