import sys
from pathlib import Path

# 앱 모듈은 app/ 루트 기준 임포트 (from services..., from core...) — 컨테이너의 /app 과 동일하게 맞춘다
APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
