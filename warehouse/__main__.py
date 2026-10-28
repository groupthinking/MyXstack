"""Run python -m warehouse --help. No server or background workers start."""
import argparse
import json
import os
from pathlib import Path

from .core import connect, evaluate, ingest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, help='Explicit local SQLite path, separate from the timeline database')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init')
    imp = commands.add_parser('import')
    imp.add_argument('file', type=Path, help='JSON array of supplied research records; URLs are not fetched')
    ev = commands.add_parser('evaluate')
    ev.add_argument('version_id')
    ev.add_argument('--live', action='store_true', help='Send this version to Jev using TYPESAFE_API_KEY')
    commands.add_parser('status')
    args = parser.parse_args()
    db = connect(args.db)
    try:
        if args.command == 'import':
            records = json.loads(args.file.read_text())
            if not isinstance(records, list) or len(records) > 1000:
                raise ValueError('Import requires an array of at most 1000 records')
            result = ingest(db, records)
        elif args.command == 'evaluate':
            result = evaluate(db, args.version_id, os.getenv('TYPESAFE_API_KEY') if args.live else None)
        else:
            result = {table: db.execute('SELECT count(*) FROM ' + table).fetchone()[0]
                      for table in ('sources', 'items', 'versions', 'decisions')}
        print(json.dumps(result, indent=2))
    finally:
        db.close()


if __name__ == '__main__':
    main()
