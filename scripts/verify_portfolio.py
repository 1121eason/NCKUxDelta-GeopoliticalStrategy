#!/usr/bin/env python3
"""Check reviewed public files, local links and the aggregate audit crosswalk."""
import json
import re
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def require(ok, message):
    if not ok:
        raise SystemExit('FAIL: ' + message)


files = sorted(p for p in ROOT.rglob('*') if p.is_file()
               and '.git' not in p.parts and '__pycache__' not in p.parts
               and p.name != '.DS_Store')
allowed = {'.md', '.svg', '.json', '.py'}
for p in files:
    rel = p.relative_to(ROOT)
    require(p.name == '.gitignore' or p.suffix in allowed,
            f'Unreviewed public file: {rel}')
    require(not any(part in {'private', '.private', 'source'} for part in rel.parts),
            f'Private material in public tree: {rel}')
    content = p.read_text()
    require(not re.search(r'R\d{8}|[\w.+-]+@gs\.ncku\.edu\.tw', content),
            f'Student identifier/contact in {rel}')
    require('\x00' not in content and '\ufffd' not in content,
            f'Encoding artifact in {rel}')

links = 0
for p in ROOT.rglob('*.md'):
    for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', p.read_text()):
        if '://' in target or target.startswith('mailto:'):
            continue
        name = unquote(target.split('#')[0])
        dest = (p.parent / name).resolve() if name else p.resolve()
        require(dest.is_relative_to(ROOT), f'Link outside public root: {target}')
        require(dest.is_file(), f'Broken link in {p.name}: {target}')
        links += 1

for p in (ROOT / 'assets').glob('*.svg'):
    node = ET.parse(p).getroot()
    require(node.tag == '{http://www.w3.org/2000/svg}svg', 'Invalid SVG root')
    require(node.find('{http://www.w3.org/2000/svg}title') is not None,
            f'Accessible title missing: {p.name}')

data = json.loads((ROOT / 'data/research-audit.json').read_text())
require(data['source']['doi'] == '10.1177/01492063251323849', 'Research DOI')
require(data['source']['pdf_page'] == 21 and data['source']['table'] == 2,
        'Table identification')
rows = data['hypothesis_specific_models']
require([r['id'] for r in rows] == ['H1', 'H2', 'H3', 'H4', 'H5'], 'Hypothesis IDs')
require([r['model'] for r in rows] == ['M2', 'M3', 'M4', 'M5', 'M6'],
        'Hypothesis-specific model mapping')
review = (ROOT / 'docs/research-review.zh-TW.md').read_text()
for r in rows:
    require(r['coefficient'] != r['slide_coefficient'], f"Audit discrepancy missing: {r['id']}")
    require(f"{r['coefficient']:.3f}" in review
            and f"{r['slide_coefficient']:.3f}" in review,
            f"Research table and JSON diverge: {r['id']}")
    require(0 <= float(r['p_as_printed']) < .05, 'Hypothesis-specific p value')
    if r['p_as_printed'] == '.000':
        require(r['p_display'] == '< .001', 'Rounded zero misrepresented')
for c in data['selected_full_model_caveats']:
    require(c['p'] > .05, 'Expected full-model caveat absent')
    require(f"{c['p']:.3f}".lstrip('0') in review, 'Full-model caveat missing in prose')
require('one-third' in data['relocation_conflict']['group_paper']['reported_share'],
        'Paper relocation conflict missing')
require('60%' in data['relocation_conflict']['group_slides']['reported_share'],
        'Slide relocation conflict missing')
print(f'PASS: {len(files)} public files; {links} local links; 2 accessible SVGs; '
      '5 model/slide crosswalks; 3 full-model caveats; public-file boundary scan.')
print('Scope: consistency only. No regression replication or company outcome validation.')
