"""
LLM 기반 파일 분류 모듈

여러 LLM 제공자(Claude, OpenAI, Gemini, Ollama 등)를 지원하는
지능형 파일 분류 시스템
"""

import os
import json
from typing import Optional, Dict, List, Any
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """LLM 설정"""
    provider: str = "none"  # none, claude, openai, gemini, ollama
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None  # Ollama 등을 위한 커스텀 URL
    max_tokens: int = 500
    temperature: float = 0.3


class LLMProvider(ABC):
    """LLM 제공자 추상 클래스"""
    
    @abstractmethod
    def classify_file(self, filename: str, content_preview: str, 
                     available_categories: List[str]) -> Dict[str, Any]:
        """
        파일 분류
        
        Args:
            filename: 파일명
            content_preview: 파일 내용 미리보기
            available_categories: 사용 가능한 카테고리 목록
            
        Returns:
            {
                "category": "카테고리명",
                "confidence": 0.95,
                "reasoning": "분류 이유"
            }
        """
        pass


class ClaudeProvider(LLMProvider):
    """Anthropic Claude 제공자"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = config.model or "claude-3-5-sonnet-20241022"
        
    def classify_file(self, filename: str, content_preview: str,
                     available_categories: List[str]) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("Claude API 키가 필요합니다")
            
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.api_key)
            
            prompt = f"""다음 파일을 분류해주세요.

파일명: {filename}
내용 미리보기:
{content_preview[:1000]}

사용 가능한 카테고리: {', '.join(available_categories)}

JSON 형식으로 응답해주세요:
{{
    "category": "가장 적합한 카테고리",
    "confidence": 0.0-1.0 사이의 확신도,
    "reasoning": "분류 이유 (한 문장)"
}}

파일의 내용, 이름, 확장자를 종합적으로 고려하여 가장 적합한 카테고리를 선택하세요."""

            message = client.messages.create(
                model=self.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            return json.loads(response_text)
            
        except Exception as e:
            return {
                "category": available_categories[0] if available_categories else "기타",
                "confidence": 0.1,
                "reasoning": f"LLM 오류: {str(e)}"
            }


class OpenAIProvider(LLMProvider):
    """OpenAI GPT 제공자"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        self.model = config.model or "gpt-4o-mini"
        
    def classify_file(self, filename: str, content_preview: str,
                     available_categories: List[str]) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("OpenAI API 키가 필요합니다")
            
        try:
            import openai
            
            client = openai.OpenAI(api_key=self.api_key)
            
            prompt = f"""다음 파일을 분류해주세요.

파일명: {filename}
내용 미리보기:
{content_preview[:1000]}

사용 가능한 카테고리: {', '.join(available_categories)}

JSON 형식으로 응답해주세요:
{{
    "category": "가장 적합한 카테고리",
    "confidence": 0.0-1.0 사이의 확신도,
    "reasoning": "분류 이유 (한 문장)"
}}"""

            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            return {
                "category": available_categories[0] if available_categories else "기타",
                "confidence": 0.1,
                "reasoning": f"LLM 오류: {str(e)}"
            }


class GeminiProvider(LLMProvider):
    """Google Gemini 제공자"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("GOOGLE_API_KEY")
        self.model = config.model or "gemini-1.5-flash"
        
    def classify_file(self, filename: str, content_preview: str,
                     available_categories: List[str]) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("Gemini API 키가 필요합니다")
            
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)
            
            prompt = f"""다음 파일을 분류해주세요.

파일명: {filename}
내용 미리보기:
{content_preview[:1000]}

사용 가능한 카테고리: {', '.join(available_categories)}

JSON 형식으로 응답해주세요:
{{
    "category": "가장 적합한 카테고리",
    "confidence": 0.0-1.0 사이의 확신도,
    "reasoning": "분류 이유 (한 문장)"
}}"""

            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": self.config.temperature,
                    "max_output_tokens": self.config.max_tokens,
                }
            )
            
            return json.loads(response.text)
            
        except Exception as e:
            return {
                "category": available_categories[0] if available_categories else "기타",
                "confidence": 0.1,
                "reasoning": f"LLM 오류: {str(e)}"
            }


class GeminiCLIProvider(LLMProvider):
    """Gemini CLI 제공자 (gemini 명령어 사용)"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.model = config.model or "gemini-2.5-flash"
        self._check_cli_available()

    def _check_cli_available(self) -> bool:
        """Gemini CLI 사용 가능 여부 확인"""
        import subprocess
        try:
            result = subprocess.run(
                ["gemini", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def classify_file(self, filename: str, content_preview: str,
                     available_categories: List[str]) -> Dict[str, Any]:
        import subprocess
        import tempfile

        prompt = f"""다음 파일을 분류해주세요.

파일명: {filename}
내용 미리보기:
{content_preview[:2000]}

사용 가능한 카테고리: {', '.join(available_categories)}

반드시 아래 JSON 형식으로만 응답해주세요 (다른 텍스트 없이):
{{"category": "가장 적합한 카테고리", "confidence": 0.0-1.0, "reasoning": "분류 이유"}}"""

        try:
            # gemini CLI 호출
            result = subprocess.run(
                ["gemini", "-m", self.model, prompt],
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8'
            )

            if result.returncode != 0:
                raise Exception(f"Gemini CLI 오류: {result.stderr}")

            response_text = result.stdout.strip()

            # JSON 추출 (응답에서 JSON 부분만 파싱)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
            else:
                raise Exception("JSON 응답을 찾을 수 없음")

        except subprocess.TimeoutExpired:
            return {
                "category": available_categories[0] if available_categories else "기타",
                "confidence": 0.1,
                "reasoning": "Gemini CLI 타임아웃"
            }
        except Exception as e:
            return {
                "category": available_categories[0] if available_categories else "기타",
                "confidence": 0.1,
                "reasoning": f"Gemini CLI 오류: {str(e)}"
            }

    def classify_files_batch(self, files: List[Dict],
                            available_categories: List[str]) -> List[Dict[str, Any]]:
        """
        여러 파일을 한 번에 분류 (배치 처리)

        Args:
            files: [{"filename": "...", "content_preview": "..."}] 리스트
            available_categories: 사용 가능한 카테고리 목록

        Returns:
            분류 결과 리스트
        """
        import subprocess

        # 배치 프롬프트 생성
        file_list = "\n\n".join([
            f"[파일 {i+1}]\n파일명: {f['filename']}\n내용: {f['content_preview'][:500]}"
            for i, f in enumerate(files[:20])  # 최대 20개
        ])

        prompt = f"""다음 파일들을 분류해주세요.

{file_list}

사용 가능한 카테고리: {', '.join(available_categories)}

각 파일에 대해 JSON 배열로 응답해주세요:
[{{"filename": "파일명", "category": "카테고리", "confidence": 0.0-1.0, "reasoning": "이유"}}, ...]"""

        try:
            result = subprocess.run(
                ["gemini", "-m", self.model, prompt],
                capture_output=True,
                text=True,
                timeout=120,
                encoding='utf-8'
            )

            if result.returncode != 0:
                raise Exception(f"Gemini CLI 오류: {result.stderr}")

            response_text = result.stdout.strip()

            # JSON 배열 추출
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
            else:
                raise Exception("JSON 배열을 찾을 수 없음")

        except Exception as e:
            # 실패 시 개별 파일 기본값 반환
            return [{
                "filename": f["filename"],
                "category": available_categories[0] if available_categories else "기타",
                "confidence": 0.1,
                "reasoning": f"배치 처리 실패: {str(e)}"
            } for f in files]


class OllamaProvider(LLMProvider):
    """Ollama 로컬 LLM 제공자"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url or "http://localhost:11434"
        self.model = config.model or "llama3.2"
    
    @staticmethod
    def list_models(base_url: str = "http://localhost:11434") -> List[str]:
        """사용 가능한 Ollama 모델 목록"""
        try:
            import requests
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except:
            return []
    
    @staticmethod
    def pull_model(model_name: str, base_url: str = "http://localhost:11434") -> bool:
        """모델 다운로드"""
        try:
            import requests
            response = requests.post(
                f"{base_url}/api/pull",
                json={"name": model_name},
                timeout=300  # 5분
            )
            return response.status_code == 200
        except:
            return False
        
    def classify_file(self, filename: str, content_preview: str,
                     available_categories: List[str]) -> Dict[str, Any]:
        try:
            import requests
            
            prompt = f"""다음 파일을 분류해주세요.

파일명: {filename}
내용 미리보기:
{content_preview[:1000]}

사용 가능한 카테고리: {', '.join(available_categories)}

JSON 형식으로만 응답해주세요:
{{
    "category": "가장 적합한 카테고리",
    "confidence": 0.0-1.0 사이의 확신도,
    "reasoning": "분류 이유 (한 문장)"
}}"""

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.config.temperature,
                        "num_predict": self.config.max_tokens,
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return json.loads(result["response"])
            else:
                raise Exception(f"Ollama API 오류: {response.status_code}")
                
        except Exception as e:
            return {
                "category": available_categories[0] if available_categories else "기타",
                "confidence": 0.1,
                "reasoning": f"LLM 오류: {str(e)}"
            }


class LLMClassifier:
    """LLM 기반 파일 분류기"""

    PROVIDERS = {
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "gemini-cli": GeminiCLIProvider,
        "ollama": OllamaProvider,
    }
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.provider: Optional[LLMProvider] = None
        
        if config.provider != "none" and config.provider in self.PROVIDERS:
            try:
                provider_class = self.PROVIDERS[config.provider]
                self.provider = provider_class(config)
            except Exception as e:
                print(f"LLM 제공자 초기화 실패 ({config.provider}): {e}")
                self.provider = None
    
    def is_available(self) -> bool:
        """LLM 사용 가능 여부"""
        return self.provider is not None
    
    def classify_file(self, filename: str, content_preview: str,
                     available_categories: List[str]) -> Dict[str, Any]:
        """
        파일 분류
        
        Args:
            filename: 파일명
            content_preview: 파일 내용 미리보기
            available_categories: 사용 가능한 카테고리 목록
            
        Returns:
            분류 결과 딕셔너리
        """
        if not self.provider:
            return {
                "category": "기타",
                "confidence": 0.0,
                "reasoning": "LLM 사용 불가"
            }
        
        try:
            return self.provider.classify_file(filename, content_preview, available_categories)
        except Exception as e:
            return {
                "category": available_categories[0] if available_categories else "기타",
                "confidence": 0.0,
                "reasoning": f"분류 실패: {str(e)}"
            }


def create_llm_classifier(
    provider: str = "none",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> LLMClassifier:
    """
    LLM 분류기 생성 헬퍼 함수
    
    Args:
        provider: LLM 제공자 (none, claude, openai, gemini, ollama)
        api_key: API 키
        model: 모델 이름
        **kwargs: 추가 설정
        
    Returns:
        LLMClassifier 인스턴스
    """
    config = LLMConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        **kwargs
    )
    return LLMClassifier(config)
