#!/usr/bin/env python3
"""
Automated generator for the Clinical Evidence Index study pages and overview.
Single source of truth: fern/data/studies.json.

Design decisions per the 8/6 revision request:
  - Study pages use a metadata table (title/authors/journal/year/country/
    dosing/DOI) instead of a wall of bold-label paragraphs.
  - Terminology standardized to "lisdexamfetamine" in generated headers/
    categories; original published study titles are left verbatim (not
    altered) with a one-line glossary note reconciling LDX <-> lisdexamfetamine.
  - Evidence overview uses per-category markdown tables (Study | Year |
    Country | DOI) instead of a Card per study - far more scannable and
    surfaces country/DOI as the site owner asked for.
  - No study-count clutter, no "U.S. FDA" branding, no throat-clearing intro
    text.
  - Sidebar nav labels are truncated (~48 chars) instead of showing full
    study titles, which were dominating the sidebar width.
"""

import json
import re
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FERN = ROOT / 'fern'
PAGES = FERN / 'docs' / 'pages'
DOCS_YML = FERN / 'docs.yml'
STUDIES_JSON = FERN / 'data' / 'studies.json'


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def categorize(title: str) -> str:
    t = title.lower()
    if 'lisdexamfetamine' in t or re.search(r'\bldx\b', t):
        return 'Lisdexamfetamine'
    if 'adderall' in t or 'mixed amphetamine' in t or re.search(r'\bmas\b', t):
        return 'Adderall / Mixed Amphetamine Salts'
    if 'methylphenidate' in t or re.search(r'\bmph\b', t) or 'dexmethylphenidate' in t:
        return 'Methylphenidate'
    if 'atomoxetine' in t:
        return 'Atomoxetine'
    return 'General ADHD Research'


CATEGORY_ORDER = [
    'Lisdexamfetamine',
    'Adderall / Mixed Amphetamine Salts',
    'Methylphenidate',
    'Atomoxetine',
    'General ADHD Research',
]


def truncate(text: str, length: int = 48) -> str:
    if len(text) <= length:
        return text
    return text[:length].rstrip() + '...'


def escape_table_cell(text: str) -> str:
    return (text or '').replace('|', '\\|').replace('\n', ' ')


def build_study_page(study: dict) -> str:
    title = study['title']
    slug = f"study-{study['id']}-{slugify(title)}"[:80]
    authors = study.get('authors', '')
    journal = study.get('journal', '')
    year = study.get('year', '')
    country = study.get('country', '')
    language = study.get('language', '')
    dosing = study.get('dosing', '')
    findings = study.get('findings', '')
    doi = study.get('doi', '')

    lines = [
        '---',
        f'title: "{title}"',
        f'slug: {slug}',
        '---',
        '',
        '| | |',
        '|---|---|',
        f'| **Journal** | {escape_table_cell(journal)} ({year}) |',
        f'| **Authors** | {escape_table_cell(authors)} |',
        f'| **Country** | {escape_table_cell(country)} |',
        f'| **Language** | {escape_table_cell(language)} |',
        f'| **Dosing regimen studied** | {escape_table_cell(dosing)} |',
        f'| **Source** | [{escape_table_cell(doi)}](https://pubmed.ncbi.nlm.nih.gov/{doi}) |',
        '',
        '## Key findings',
        '',
        findings,
        '',
    ]
    return '\n'.join(lines), slug


def build_overview_page(studies: list) -> str:
    cats = {}
    for s in studies:
        cat = categorize(s['title'])
        cats.setdefault(cat, []).append(s)

    lines = [
        '---',
        'title: Evidence Overview',
        'slug: evidence-overview',
        '---',
        '',
        '<Note>',
        'LDX and lisdexamfetamine refer to the same compound (lisdexamfetamine '
        'dimesylate). Study titles are shown as originally published; category '
        'headings below use the full name.',
        '</Note>',
        '',
    ]

    for cat in CATEGORY_ORDER:
        studies_in_cat = cats.get(cat, [])
        if not studies_in_cat:
            continue
        lines.append(f'## {cat}')
        lines.append('')
        lines.append('| Study | Year | Country | Source |')
        lines.append('|---|---|---|---|')
        for s in sorted(studies_in_cat, key=lambda x: x.get('year', 0)):
            slug = f"study-{s['id']}-{slugify(s['title'])}"[:80]
            title_cell = escape_table_cell(s['title'])
            year = s.get('year', '')
            country = escape_table_cell(s.get('country', ''))
            doi = escape_table_cell(s.get('doi', ''))
            lines.append(f"| [{title_cell}](/{slug}) | {year} | {country} | {doi} |")
        lines.append('')

    return '\n'.join(lines).rstrip() + '\n'


def update_nav(studies: list):
    with open(DOCS_YML) as f:
        d = yaml.safe_load(f)

    d['title'] = 'Clinical Evidence Index'

    if 'page-actions' in d.get('theme', {}):
        del d['theme']['page-actions']

    items = []
    for s in studies:
        title = s['title']
        slug = f"study-{s['id']}-{slugify(title)}"[:80]
        items.append({
            'page': truncate(title, 48),
            'path': f'docs/pages/{slug}.mdx',
            'icon': 'fa-regular fa-file-lines',
        })

    for t in d['navigation']:
        if t.get('tab') == 'evidence':
            new_layout = [{
                'page': 'Evidence Overview',
                'path': 'docs/pages/evidence-overview.mdx',
                'icon': 'fa-regular fa-list',
            }]
            new_layout.append({'section': 'Studies', 'contents': items})
            t['layout'] = new_layout

    with open(DOCS_YML, 'w') as f:
        yaml.dump(d, f, sort_keys=False, default_flow_style=False, width=200, allow_unicode=True)


def main():
    data = json.loads(STUDIES_JSON.read_text())
    studies = data['studies']

    # remove old flat study-*.mdx pages so slugs don't collide with any stale files
    for f in PAGES.glob('study-*.mdx'):
        f.unlink()

    for study in studies:
        content, slug = build_study_page(study)
        (PAGES / f'{slug}.mdx').write_text(content)

    (PAGES / 'evidence-overview.mdx').write_text(build_overview_page(studies))

    update_nav(studies)

    print(f'Generated {len(studies)} study pages + overview page.')


if __name__ == '__main__':
    main()
