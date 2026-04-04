from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
RAW_DATA_DIR = DATA_DIR / 'raw'
SAMPLE_DATA_DIR = DATA_DIR / 'sample'
OUTPUT_DIR = PROJECT_ROOT / 'outputs'
LOG_DIR = PROJECT_ROOT / 'logs'
DB_PATH = PROJECT_ROOT / 'inventory.db'
DB_URL = f"sqlite:///{DB_PATH}"
CHUNK_SIZE = 300_000
SAMPLE_ROWS = 5_000

OTIF_SLA_DAYS = 14
