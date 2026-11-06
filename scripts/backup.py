"""Cópia consistente do SQLite usando a API nativa backup()."""
import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def backup(source: Path, destination: Path) -> None:
    if not source.exists():
        raise SystemExit('Banco não encontrado. Inicialize a aplicação antes de fazer backup.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)
    try:
        destination.chmod(0o600)
    except OSError:
        pass
    print('Cópia criada:', destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Criar backup consistente da base SQLite')
    parser.add_argument('--db', default=os.getenv('DB_PATH', str(ROOT/'instance'/'maravilha.db')))
    parser.add_argument('--dest', default=str(ROOT/'backups'/f'maravilha-{datetime.now():%Y%m%d-%H%M%S}.db'))
    args = parser.parse_args()
    backup(Path(args.db), Path(args.dest))
