"""
prompts.py — 도메인 프롬프트 템플릿 로더 (도메인 공통)

프롬프트 1개 = YAML 파일 1개:
    parser: summary_themes | plain     # 응답 후처리 방식 (선택, 기본 plain)
    params:                            # LLM 생성 파라미터 (선택)
      max_tokens: 4000
      temperature: 0.1
    system: |-
      시스템 프롬프트 (Jinja2)
    user: |-
      유저 프롬프트 (Jinja2, {{ var }} 치환)

해석 순서: {name}.{doc_type}.yaml → {name}.yaml → FileNotFoundError
( 도메인 작성 시 누락을 즉시 발견하기 위해 조용한 fallback 금지 시킴)
"""
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

_jinja = Environment(undefined=StrictUndefined, keep_trailing_newline=False)


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    system: str
    user: str
    parser: str = "plain"
    params: dict = field(default_factory=dict)

    def render(self, **vars) -> tuple[str, str, dict]:
        """(system, user, params) 반환. system/user 모두 Jinja2 치환."""
        system = _jinja.from_string(self.system).render(**vars)
        user = _jinja.from_string(self.user).render(**vars)
        return system, user, dict(self.params)


class PromptLibrary:
    """도메인 프롬프트 디렉토리에서 YAML 템플릿을 로드 (파일 단위 캐싱)."""

    def __init__(self, prompts_dir: str | Path):
        self._dir = Path(prompts_dir)

    def get(self, name: str, doc_type: str | None = None) -> PromptTemplate:
        if doc_type:
            variant = self._dir / f"{name}.{doc_type}.yaml"
            if variant.is_file():
                return _load_template(str(variant), name)
        base = self._dir / f"{name}.yaml"
        if base.is_file():
            return _load_template(str(base), name)
        tried = f"{name}.{doc_type}.yaml, {name}.yaml" if doc_type else f"{name}.yaml"
        raise FileNotFoundError(
            f"프롬프트 템플릿 없음: {self._dir} 에서 시도한 파일 — {tried}"
        )


@lru_cache(maxsize=256)
def _load_template(path: str, name: str) -> PromptTemplate:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "system" not in data or "user" not in data:
        raise ValueError(f"프롬프트 YAML 형식 오류 ({path}): system/user 키 필수")
    return PromptTemplate(
        name=name,
        system=str(data["system"]).rstrip("\n"),
        user=str(data["user"]).rstrip("\n"),
        parser=data.get("parser", "plain"),
        params=data.get("params") or {},
    )


def get_prompt(name: str, doc_type: str | None = None) -> PromptTemplate:
    """활성 도메인 프로파일의 프롬프트 디렉토리에서 템플릿 조회 (편의 함수)."""
    from domains import get_active_profile

    profile = get_active_profile()
    return PromptLibrary(profile.prompts_path).get(name, doc_type)
