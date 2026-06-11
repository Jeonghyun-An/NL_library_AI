"""
domains — 도메인 프로파일 레지스트리

활성 프로파일은 Settings.DOMAIN_PROFILE (env) 로 선택한다.
새 도메인 추가: domains/{name}/profile.py 에 PROFILE = DomainProfile(...) 정의.
"""
import importlib
from functools import lru_cache

from domains.base import DomainProfile


def _load_profile(name: str) -> DomainProfile:
    mod = importlib.import_module(f"domains.{name}.profile")
    profile = getattr(mod, "PROFILE", None)
    if not isinstance(profile, DomainProfile):
        raise TypeError(f"domains.{name}.profile.PROFILE 이 DomainProfile 이 아닙니다")
    return profile


@lru_cache(maxsize=4)
def get_active_profile() -> DomainProfile:
    from core.config import get_settings

    return _load_profile(get_settings().DOMAIN_PROFILE)
