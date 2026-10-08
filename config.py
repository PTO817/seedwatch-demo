"""Public demo only. Environment variables cannot enable private mode."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent
MODE = 'demo'
DEMO = True
LOCAL = False
TEST_WORKSPACE = False
DATABASE = ROOT / 'runtime/demo-v2.db'
RUNTIME = ROOT / 'runtime/demo'
TIMEZONE = 'America/New_York'
