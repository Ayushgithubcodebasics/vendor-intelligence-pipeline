from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from src.config import CHUNK_SIZE, DB_URL, OUTPUT_DIR, RAW_DATA_DIR
from src.utils import get_logger

logger = get_logger(__name__)


def ingest_csv_to_sqlite(path: Path, table_name: str, engine) -> None:
    staging_table = f"{table_name}__staging"
    first = True
    for chunk in pd.read_csv(path, chunksize=CHUNK_SIZE, low_memory=False):
        chunk.to_sql(staging_table, con=engine, if_exists='replace' if first else 'append', index=False, method='multi')
        first = False
    with engine.begin() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
        conn.execute(text(f'ALTER TABLE "{staging_table}" RENAME TO "{table_name}"'))
    logger.info('Loaded %s into table %s', path.name, table_name)


def main() -> None:
    engine = create_engine(DB_URL, echo=False)
    for csv_path in sorted(RAW_DATA_DIR.glob('*.csv')):
        ingest_csv_to_sqlite(csv_path, csv_path.stem, engine)
    corrected = OUTPUT_DIR / 'vendor_sales_summary_corrected.csv'
    if corrected.exists():
        pd.read_csv(corrected).to_sql('vendor_sales_summary_corrected', con=engine, if_exists='replace', index=False)
        logger.info('Loaded corrected summary into SQLite')


if __name__ == '__main__':
    main()
