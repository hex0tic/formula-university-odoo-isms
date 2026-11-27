"""Validate custom Odoo addon sources without running addon code."""
import ast
import csv
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

addons = Path(__file__).resolve().parents[2] / 'addons'
counts = dict(py=0, xml=0, csv=0, js=0)
errors = []

for path in sorted(addons.rglob('*')):
    ext = path.suffix[1:]
    if ext not in counts or not path.is_file():
        continue
    try:
        source = path.read_text(encoding='utf-8-sig')
        if ext == 'py':
            ast.parse(source, filename=str(path))
            if path.name == '__manifest__.py':
                ast.literal_eval(source)
        elif ext == 'xml':
            ET.fromstring(source)
        elif ext == 'csv':
            rows = list(csv.reader(source.splitlines(keepends=True), strict=True))
            if not rows or any(row and len(row) != len(rows[0]) for row in rows):
                raise ValueError('CSV column counts differ or header is missing')
        else:
            result = subprocess.run(['node', '--input-type=module', '--check'], input=source,
                                    text=True, capture_output=True, check=False)
            if result.returncode:
                raise ValueError(result.stderr.strip())
        counts[ext] += 1
    except (ValueError, SyntaxError, UnicodeError, csv.Error, ET.ParseError) as exc:
        errors.append(f'{path.relative_to(addons)}: {exc}')

for error in errors:
    print(error, file=sys.stderr)
print(', '.join(f'{ext}: {count}' for ext, count in counts.items()))
sys.exit(bool(errors))
