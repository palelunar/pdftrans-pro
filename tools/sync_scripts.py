"""Publish common scripts from the Claude/Open Agent package to the DSH package.

Run with --check in CI; platform-specific SKILL.md files are never copied.
"""
import argparse
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
source = root / 'claude-code/pdftrans-pro/scripts'
target = root / 'deepseek-harness/pdftrans-pro/scripts'
different = []
for item in sorted(source.glob('*.py')):
    destination = target / item.name
    if not destination.exists() or destination.read_bytes() != item.read_bytes():
        different.append(item.name)
        if not args.check:
            shutil.copy2(item, destination)
extras = sorted(p.name for p in target.glob('*.py') if not (source / p.name).exists())
if extras:
    sys.exit('Unexpected DSH scripts; review manually: ' + ', '.join(extras))
if args.check and different:
    sys.exit('Scripts differ: ' + ', '.join(different))
print('Scripts match.' if args.check else 'Synchronized: ' + ', '.join(different))
