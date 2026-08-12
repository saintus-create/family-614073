#!/usr/bin/env python3
"""
Build the Clinical Evidence Index from fern/data/studies.json.

The dataset is produced by scripts/fetch_pubmed.py straight from the NCBI
E-utilities API, so every record here traces to a real PubMed entry. This
script only renders; it never invents metadata.

Catalogue model (mirrors how a research database is organised):

    Browse           entry point + how the index is built
    By drug class    one index page per collection
    By study design  RCTs, meta-analyses, cohorts, ...
    By topic         safety, pharmacokinetics, abuse liability, ...
    Studies          one record page per study

Record pages use Fern's native components only -- Badge, Callout, Card,
CardGroup, Accordion, Tabs, Steps -- with no custom CSS or bespoke markup.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
FERN = ROOT / 'fern'
PAGES = FERN / 'docs' / 'pages'
STUDIES_DIR = PAGES / 'studies'
INDEX_DIR = PAGES / 'index'
LABELS_DIR = PAGES / 'labels'
DOCS_YML = FERN / 'docs.yml'
STUDIES_JSON = FERN / 'data' / 'studies.json'
LABELS_JSON = FERN / 'data' / 'labels.json'

REGION_ORDER = [
    'North America', 'Europe', 'Asia', 'Oceania',
    'Latin America', 'Middle East', 'Africa',
]

REGION_ICON = {
    'North America': 'fa-regular fa-earth-americas',
    'Latin America': 'fa-regular fa-earth-americas',
    'Europe': 'fa-regular fa-earth-europe',
    'Asia': 'fa-regular fa-earth-asia',
    'Middle East': 'fa-regular fa-earth-asia',
    'Africa': 'fa-regular fa-earth-africa',
    'Oceania': 'fa-regular fa-earth-oceania',
}

# Mirrors COUNTRY_REGION in scripts/fetch_pubmed.py; used to nest countries
# under their region in the sidebar.
COUNTRY_REGION_LOOKUP = {
    'United States': 'North America', 'Canada': 'North America', 'Mexico': 'North America',
    'Brazil': 'Latin America', 'Argentina': 'Latin America', 'Chile': 'Latin America',
    'Colombia': 'Latin America',
    'United Kingdom': 'Europe', 'Germany': 'Europe', 'Netherlands': 'Europe',
    'Sweden': 'Europe', 'Denmark': 'Europe', 'Norway': 'Europe', 'Finland': 'Europe',
    'Iceland': 'Europe', 'Spain': 'Europe', 'Italy': 'Europe', 'France': 'Europe',
    'Belgium': 'Europe', 'Switzerland': 'Europe', 'Austria': 'Europe', 'Ireland': 'Europe',
    'Portugal': 'Europe', 'Poland': 'Europe', 'Czech Republic': 'Europe',
    'Hungary': 'Europe', 'Greece': 'Europe', 'Russia': 'Europe',
    'Turkey': 'Middle East', 'Israel': 'Middle East', 'Iran': 'Middle East',
    'Saudi Arabia': 'Middle East',
    'China': 'Asia', 'Taiwan': 'Asia', 'Hong Kong': 'Asia', 'Japan': 'Asia',
    'South Korea': 'Asia', 'India': 'Asia', 'Singapore': 'Asia', 'Thailand': 'Asia',
    'Malaysia': 'Asia',
    'Egypt': 'Africa', 'South Africa': 'Africa', 'Nigeria': 'Africa',
    'Australia': 'Oceania', 'New Zealand': 'Oceania',
}

REGIMEN_ORDER = [
    'Once daily',
    'Twice daily',
    'Three times daily',
    'Divided / multiple daily doses',
    'Extended release',
    'Immediate release',
    'Titrated to effect',
    'Single dose (study)',
]

REGIMEN_ICON = {
    'Once daily': 'fa-regular fa-sun',
    'Twice daily': 'fa-regular fa-clock',
    'Three times daily': 'fa-regular fa-hourglass-half',
    'Divided / multiple daily doses': 'fa-regular fa-layer-group',
    'Extended release': 'fa-regular fa-chart-line',
    'Immediate release': 'fa-regular fa-bolt',
    'Titrated to effect': 'fa-regular fa-sliders',
    'Single dose (study)': 'fa-regular fa-1',
}

# Boxed warnings and controlled-substance status are the label sections a
# reader most needs up front, so they render as their own callouts.
LABEL_SECTION_ORDER = [
    'Boxed warning',
    'Indications and usage',
    'Dosage and administration',
    'Dosage detail',
    'Dosage forms and strengths',
    'Contraindications',
    'Controlled substance',
    'Abuse',
    'Dependence',
    'Pregnancy',
    'Lactation',
    'Pediatric use',
    'Geriatric use',
]

# Badge intents per study design, strongest evidence first.
DESIGN_ORDER = [
    'Meta-analysis',
    'Systematic review',
    'Randomized controlled trial',
    'Clinical trial',
    'Cohort study',
    'Case-control study',
    'Cross-sectional study',
    'Pharmacokinetic study',
    'Practice guideline',
    'Review',
    'Case report',
    'Other',
]

DESIGN_INTENT = {
    'Meta-analysis': 'success',
    'Systematic review': 'success',
    'Randomized controlled trial': 'check',
    'Clinical trial': 'check',
    'Cohort study': 'info',
    'Case-control study': 'info',
    'Cross-sectional study': 'info',
    'Pharmacokinetic study': 'info',
    'Practice guideline': 'launch',
    'Review': 'note',
    'Case report': 'warning',
    'Other': 'note',
}

DESIGN_ICON = {
    'Meta-analysis': 'fa-regular fa-layer-group',
    'Systematic review': 'fa-regular fa-list-check',
    'Randomized controlled trial': 'fa-regular fa-flask',
    'Clinical trial': 'fa-regular fa-vial',
    'Cohort study': 'fa-regular fa-users',
    'Case-control study': 'fa-regular fa-code-compare',
    'Cross-sectional study': 'fa-regular fa-chart-simple',
    'Pharmacokinetic study': 'fa-regular fa-chart-line',
    'Practice guideline': 'fa-regular fa-scale-balanced',
    'Review': 'fa-regular fa-book-open',
    'Case report': 'fa-regular fa-file-medical',
    'Other': 'fa-regular fa-file-lines',
}

TOPIC_ICON = {
    'Efficacy': 'fa-regular fa-bullseye',
    'Safety & tolerability': 'fa-regular fa-shield-halved',
    'Cardiovascular': 'fa-regular fa-heart-pulse',
    'Growth & development': 'fa-regular fa-ruler-vertical',
    'Pharmacokinetics': 'fa-regular fa-chart-line',
    'Abuse liability': 'fa-regular fa-triangle-exclamation',
    'Cognition & function': 'fa-regular fa-brain',
    'Comorbidity': 'fa-regular fa-diagram-project',
    'Sleep': 'fa-regular fa-moon',
    'Epidemiology & utilization': 'fa-regular fa-globe',
}

COLLECTION_ICON = {
    'lisdexamfetamine': 'fa-regular fa-capsules',
    'amphetamine': 'fa-regular fa-pills',
    'methylphenidate': 'fa-regular fa-tablets',
    'atomoxetine': 'fa-regular fa-prescription-bottle',
    'comparative': 'fa-regular fa-code-compare',
    'binge-eating': 'fa-regular fa-utensils',
    'trials': 'fa-regular fa-flask',
    'pharmacokinetics': 'fa-regular fa-chart-line',
    'long-term-safety': 'fa-regular fa-heart-pulse',
}

LANGUAGE_NAMES = {
    'eng': 'English', 'spa': 'Spanish', 'jpn': 'Japanese', 'ger': 'German',
    'fre': 'French', 'ita': 'Italian', 'por': 'Portuguese', 'chi': 'Chinese',
    'rus': 'Russian', 'dut': 'Dutch', 'pol': 'Polish', 'tur': 'Turkish',
    'dan': 'Danish', 'swe': 'Swedish', 'nor': 'Norwegian', 'fin': 'Finnish',
    'cze': 'Czech', 'hun': 'Hungarian', 'gre': 'Greek', 'heb': 'Hebrew',
    'kor': 'Korean', 'ara': 'Arabic', 'per': 'Persian', 'ukr': 'Ukrainian',
    'rum': 'Romanian', 'slo': 'Slovak', 'srp': 'Serbian', 'hrv': 'Croatian',
}

MAX_NAV_LABEL = 62


def slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def study_slug(s: dict) -> str:
    return f"pmid-{s['pmid']}"


def truncate(text: str, length: int = MAX_NAV_LABEL) -> str:
    text = ' '.join(text.split())
    return text if len(text) <= length else text[:length].rstrip(' ,;:') + '...'


def mdx_safe(text) -> str:
    """Neutralise characters MDX would read as JSX.

    PubMed abstracts are full of comparisons like "<18 years" and "p<0.05",
    which MDX otherwise treats as the start of a JSX tag and refuses to parse.
    Braces get the same treatment since MDX evaluates them as expressions.
    """
    return (str(text or '')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('{', '&#123;')
            .replace('}', '&#125;'))


def esc_cell(text) -> str:
    return mdx_safe(text).replace('|', '\\|').replace('\n', ' ').strip()


def yaml_quote(text: str) -> str:
    return '"' + str(text).replace('\\', '\\\\').replace('"', '\\"') + '"'


def jsx_attr(text: str) -> str:
    """Quote a value for a JSX attribute.

    JSX is not YAML: a backslash-escaped quote is a syntax error there, so any
    double quote in the value has to become an HTML entity instead. Study titles
    routinely contain quoted phrases, e.g. Not Really "The Same Thing".
    """
    return '"' + mdx_safe(text).replace('"', '&quot;') + '"'


def author_line(authors: list, limit: int = 6) -> str:
    if not authors:
        return 'No author listed'
    if len(authors) <= limit:
        return ', '.join(authors)
    return ', '.join(authors[:limit]) + f', et al. ({len(authors)} authors)'


def source_line(s: dict) -> str:
    """Journal. Year Mon;Volume(Issue):pages. doi: 10.x/y."""
    date = str(s['year'] or s.get('medline_date') or '').strip()
    if s.get('month'):
        date = f"{date} {s['month']}".strip()
    out = f"{s['journal']}. {date}" if s['journal'] else date
    vol = s.get('volume') or ''
    if vol:
        out += f";{vol}"
        if s.get('issue'):
            out += f"({s['issue']})"
    if s.get('pages'):
        out += f":{s['pages']}"
    out = out.rstrip('.') + '.'
    if s['doi']:
        out += f" doi: {s['doi']}."
    return mdx_safe(out)


def pubmed_url(pmid: str) -> str:
    return f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'


def source_links(s: dict) -> str:
    """Every identifier gets the URL scheme that actually resolves for it."""
    links = [f'[PubMed {s["pmid"]}]({pubmed_url(s["pmid"])})']
    if s['doi']:
        links.append(f'[DOI {s["doi"]}](https://doi.org/{s["doi"]})')
    if s['pmcid']:
        links.append(
            f'[{s["pmcid"]} full text](https://www.ncbi.nlm.nih.gov/pmc/articles/{s["pmcid"]}/)')
    return ' · '.join(links)


# --------------------------------------------------------------------------
# record pages
# --------------------------------------------------------------------------

def build_study_page(s: dict, related: list) -> str:
    lang = LANGUAGE_NAMES.get(s['language'], s['language'])

    lines = [
        '---',
        f'title: {yaml_quote(s["title"])}',
        f'slug: {study_slug(s)}',
        '---',
        '',
        mdx_safe(author_line(s['authors'], 24)),
        '',
        source_line(s),
        '',
        f'PMID: [{s["pmid"]}]({pubmed_url(s["pmid"])})'
        + (f' · PMCID: [{s["pmcid"]}](https://www.ncbi.nlm.nih.gov/pmc/articles/{s["pmcid"]}/)'
           if s['pmcid'] else '')
        + (f' · {mdx_safe(s["design"])}' if s['design'] and s['design'] != 'Other' else ''),
        '',
        '## Abstract',
        '',
    ]

    body = s['abstract']
    if not re.search(r'\*\*[A-Za-z][^*]*:\*\*', body) and s['conclusion']:
        # unstructured abstract: still give the conclusion its own heading
        lines += [mdx_safe(body), '', '**Conclusion:**', '',
                  mdx_safe(s['conclusion']), '']
    else:
        lines += [mdx_safe(body), '']

    if s['mesh']:
        lines += ['## MeSH terms', '',
                  '\n'.join(f'- {mdx_safe(m)}' for m in s['mesh']), '']

    if related:
        lines += ['## Similar articles', '']
        for r in related:
            lines.append(f'- [{mdx_safe(r["title"])}](/{study_slug(r)})  ')
            lines.append(f'  {mdx_safe(author_line(r["authors"], 3))} '
                         f'{source_line(r)} PMID: {r["pmid"]}')
        lines.append('')

    return '\n'.join(lines)


def pick_related(s: dict, studies: list, limit: int = 4) -> list:
    """Nearest records by shared collection, topics and MeSH terms."""
    scored = []
    s_topics, s_mesh = set(s['topics']), set(s['mesh'])
    for other in studies:
        if other['pmid'] == s['pmid']:
            continue
        score = 0
        if other['collection'] == s['collection']:
            score += 3
        score += 2 * len(s_topics & set(other['topics']))
        score += len(s_mesh & set(other['mesh']))
        if other['design'] == s['design']:
            score += 1
        if score:
            scored.append((score, other['year'] or 0, other))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [o for _, _, o in scored[:limit]]


# --------------------------------------------------------------------------
# index pages
# --------------------------------------------------------------------------

def study_table(studies: list, show: str = 'design') -> list:
    header = {
        'design': '| Study | Journal | Year | Design |',
        'topic': '| Study | Journal | Year | Design |',
    }[show]
    lines = [header, '|---|---|---|---|']
    for s in sorted(studies, key=lambda x: (-(x['year'] or 0), x['title'])):
        lines.append(
            f'| [{esc_cell(truncate(s["title"], 90))}](/{study_slug(s)}) '
            f'| {esc_cell(s["journal"])} | {s["year"] or "n.d."} | {esc_cell(s["design"])} |')
    return lines


def results_list(studies: list) -> list:
    """PubMed search-result style: title, authors, source line, PMID, conclusion."""
    rank = {name: i for i, name in enumerate(DESIGN_ORDER)}
    ordered = sorted(studies, key=lambda s: (rank.get(s['design'], 99), -(s['year'] or 0)))

    lines = []
    for s in ordered:
        lines.append(f'### [{mdx_safe(s["title"])}](/{study_slug(s)})')
        lines.append('')
        lines.append(mdx_safe(author_line(s['authors'], 8)))
        lines.append('')
        tail = f'PMID: {s["pmid"]}'
        if s['design'] and s['design'] != 'Other':
            tail += f' · {mdx_safe(s["design"])}'
        lines.append(f'{source_line(s)} {tail}')
        lines.append('')
        if s['conclusion']:
            lines.append(mdx_safe(s['conclusion']))
            lines.append('')
    return lines


def build_collection_page(coll: dict, studies: list) -> str:
    lines = [
        '---',
        f'title: {yaml_quote(coll["name"])}',
        f'slug: collection-{coll["key"]}',
        '---',
        '',
    ]
    lines += results_list(studies)
    lines += [
        '<Accordion title="Search strategy">',
        '```',
        coll['query'],
        '```',
        '</Accordion>',
        '',
    ]
    return '\n'.join(lines)


def build_design_page(design: str, studies: list) -> str:
    lines = [
        '---',
        f'title: {yaml_quote(design)}',
        f'slug: design-{slugify(design)}',
        '---',
        '',
    ]
    lines += results_list(studies)
    return '\n'.join(lines)


def build_topic_page(topic: str, studies: list) -> str:
    lines = [
        '---',
        f'title: {yaml_quote(topic)}',
        f'slug: topic-{slugify(topic)}',
        '---',
        '',
    ]
    lines += results_list(studies)
    return '\n'.join(lines)


def build_region_page(region: str, studies: list) -> str:
    countries = Counter(c for s in studies for c in s['countries']
                        if COUNTRY_REGION_LOOKUP.get(c) == region)
    lines = [
        '---',
        f'title: {yaml_quote(region)}',
        f'slug: region-{slugify(region)}',
        '---',
        '',
        ' · '.join(f'[{c}](/country-{slugify(c)})'
                   for c, _ in countries.most_common()),
        '',
    ]
    lines += results_list(studies)
    return '\n'.join(lines)


def build_country_page(country: str, studies: list) -> str:
    lines = [
        '---',
        f'title: {yaml_quote(country)}',
        f'slug: country-{slugify(country)}',
        '---',
        '',
    ]
    lines += results_list(studies)
    return '\n'.join(lines)


def build_regimen_page(regimen: str, studies: list) -> str:
    doses = Counter(d for s in studies for d in s['doses'])
    lines = [
        '---',
        f'title: {yaml_quote(regimen)}',
        f'slug: regimen-{slugify(regimen)}',
        '---',
        '',
    ]
    lines += results_list(studies)
    return '\n'.join(lines)


def build_regulatory_overview(labels: dict) -> str:
    lines = [
        '---',
        'title: Regulatory guidance',
        'subtitle: Approved prescribing information from the US FDA label archive',
        'slug: regulatory',
        '---',
        '',
        '<Callout intent="warning">',
        'Approved **US** labelling, reproduced from DailyMed '
        f'({labels["generated"]}). Requirements differ by country. Not medical advice.',
        '</Callout>',
        '',
        '## Products',
        '',
        '<CardGroup cols={2}>',
    ]
    for lab in labels['labels']:
        boxed = any(s['kind'] == 'Boxed warning' for s in lab['sections'])
        desc = lab['brands'] + (' · Boxed warning' if boxed else '')
        lines.append(
            f'  <Card title={jsx_attr(lab["name"])} '
            f'icon="fa-regular fa-file-prescription" href="/label-{lab["key"]}">')
        lines.append(f'    {mdx_safe(desc)}')
        lines.append('  </Card>')
    lines += ['</CardGroup>', '']

    lines += [
        '## Scheduling and boxed warnings at a glance',
        '',
        '| Product | Boxed warning | Controlled substance |',
        '|---|---|---|',
    ]
    for lab in labels['labels']:
        boxed = 'Yes' if any(s['kind'] == 'Boxed warning' for s in lab['sections']) else 'No'
        csa = next((s['text'] for s in lab['sections']
                    if s['kind'] == 'Controlled substance'), '')
        m = re.search(r'Schedule\s+([IVX]+)', csa)
        if m:
            sched = f'Schedule {m.group(1)}'
        elif re.search(r'not a controlled substance', csa, re.IGNORECASE):
            sched = 'Not scheduled'
        else:
            sched = 'See label'
        lines.append(
            f'| [{esc_cell(lab["name"])}](/label-{lab["key"]}) | {boxed} | {sched} |')
    lines.append('')
    return '\n'.join(lines)


def build_label_page(lab: dict) -> str:
    by_kind = defaultdict(list)
    for sec in lab['sections']:
        by_kind[sec['kind']].append(sec)

    lines = [
        '---',
        f'title: {yaml_quote(lab["name"])}',
        f'subtitle: {yaml_quote("US prescribing information · " + lab["brands"])}',
        f'slug: label-{lab["key"]}',
        '---',
        '',
    ]

    csa = next((s['text'] for s in lab['sections'] if s['kind'] == 'Controlled substance'), '')
    m = re.search(r'Schedule\s+([IVX]+)', csa)
    badges = []
    if m:
        badges.append(f'<Badge intent="warning">Schedule {m.group(1)}</Badge>')
    elif re.search(r'not a controlled substance', csa, re.IGNORECASE):
        badges.append('<Badge intent="success" minimal>Not a controlled substance</Badge>')
    if by_kind.get('Boxed warning'):
        badges.append('<Badge intent="error">Boxed warning</Badge>')
    badges.append(f'<Badge intent="info" minimal>Label published {lab["published"]}</Badge>')
    lines += [' '.join(badges), '']

    for sec in by_kind.get('Boxed warning', []):
        lines += [
            '<Callout intent="error">',
            f'**{mdx_safe(sec["title"])}**',
            '',
            mdx_safe(sec['text']),
            '</Callout>',
            '',
        ]

    lines += [
        '| | |',
        '|---|---|',
        f'| Active ingredient | {esc_cell(lab["name"])} |',
        f'| Common brand names | {esc_cell(lab["brands"])} |',
        f'| Label version | {esc_cell(lab["spl_title"])} |',
        f'| Published | {esc_cell(lab["published"])} |',
        f'| Source | [DailyMed SPL]({lab["url"]}) |',
        '',
    ]

    # Dosing gets its own section since it is the reason most people arrive.
    dosing = by_kind.get('Dosage and administration', []) + by_kind.get('Dosage detail', [])
    if dosing:
        lines += ['## Dosage and administration', '', '<AccordionGroup>']
        for sec in dosing:
            lines.append(f'  <Accordion title={jsx_attr(sec["title"])}>')
            for para in mdx_safe(sec['text']).split('\n'):
                if para.strip():
                    lines.append(f'    {para}')
            lines.append('  </Accordion>')
        lines += ['</AccordionGroup>', '']

    rest = [k for k in LABEL_SECTION_ORDER
            if k not in ('Boxed warning', 'Dosage and administration', 'Dosage detail')]
    remaining = [(k, s) for k in rest for s in by_kind.get(k, [])]
    if remaining:
        lines += ['## Full label sections', '', '<AccordionGroup>']
        for _, sec in remaining:
            lines.append(f'  <Accordion title={jsx_attr(sec["title"])}>')
            for para in mdx_safe(sec['text']).split('\n'):
                if para.strip():
                    lines.append(f'    {para}')
            lines.append('  </Accordion>')
        lines += ['</AccordionGroup>', '']

    return '\n'.join(lines)


def build_browse_page(data: dict, studies: list) -> str:
    by_coll = defaultdict(list)
    for s in studies:
        by_coll[s['collection']].append(s)
    topics = Counter(t for s in studies for t in s['topics'])
    designs = Counter(s['design'] for s in studies)

    lines = [
        '---',
        'title: Browse',
        f'subtitle: {yaml_quote(f"{len(studies)} studies")}',
        'slug: browse',
        '---',
        '',
        '## Drugs',
        '',
        '<CardGroup cols={3}>',
    ]
    for coll in data['collections']:
        items = by_coll.get(coll['key'])
        if not items:
            continue
        syn = sum(1 for s in items if s['design'] in ('Meta-analysis', 'Systematic review'))
        lines.append(
            f'  <Card title={jsx_attr(coll["name"])} '
            f'icon="{COLLECTION_ICON.get(coll["key"], "fa-regular fa-folder")}" '
            f'href="/collection-{coll["key"]}">')
        lines.append(f'    {len(items)} studies · {syn} syntheses')
        lines.append('  </Card>')
    lines += ['</CardGroup>', '', '## Topics', '', '<CardGroup cols={2}>']
    for topic, n in topics.most_common():
        lines.append(
            f'  <Card title={jsx_attr(topic)} '
            f'icon="{TOPIC_ICON.get(topic, "fa-regular fa-tag")}" '
            f'href="/topic-{slugify(topic)}">')
        lines.append(f'    {n} studies')
        lines.append('  </Card>')
    lines += ['</CardGroup>', '', '## Study designs', '', '<CardGroup cols={3}>']
    for design in DESIGN_ORDER:
        if not designs.get(design):
            continue
        lines.append(
            f'  <Card title={jsx_attr(design)} '
            f'icon="{DESIGN_ICON.get(design, "fa-regular fa-file-lines")}" '
            f'href="/design-{slugify(design)}">')
        lines.append(f'    {designs[design]} studies')
        lines.append('  </Card>')
    lines += ['</CardGroup>', '']

    regimens = Counter(r for s in studies for r in s['regimens'])
    regions = Counter(r for s in studies for r in s['regions'])
    lines += ['## Dosing regimens', '', ' · '.join(
        f'[{r}](/regimen-{slugify(r)}) ({regimens[r]})'
        for r in REGIMEN_ORDER if regimens.get(r)), '']
    lines += ['## Regions', '', ' · '.join(
        f'[{r}](/region-{slugify(r)}) ({regions[r]})'
        for r in REGION_ORDER if regions.get(r)), '']

    return '\n'.join(lines)


DISCLAIMER_TEXT = '''---
title: Disclaimer
slug: disclaimer
---

This disclaimer relates to PubMed, PubMed Central (PMC), and Bookshelf. These three resources are scientific literature databases offered to the public by the U.S. National Library of Medicine (NLM). NLM is not a publisher, but rather collects, indexes, and archives scientific literature published by other organizations. The presence of any article, book, or document in these databases does not imply an endorsement of, or concurrence with, the contents by NLM, the National Institutes of Health (NIH), or the U.S. Federal Government.

Please see more below about our content and how our databases relate to you.

## Literature Database Content

Content in NLM literature databases may be published by academic publishers or institutions, scholarly societies, or government and non-governmental organizations. To be added to a database, a publication must apply and be selected by NLM for inclusion in MEDLINE, PMC, or Bookshelf. PubMed indexes and makes searchable the contents of these databases; MEDLINE is the primary component of PubMed. Details on the content selection processes for each database can be found at:

- [MEDLINE](https://www.nlm.nih.gov/medline/medline_journal_selection.html)
- [PubMed Central](https://www.ncbi.nlm.nih.gov/pmc/pub/journalselect)
- [Bookshelf](https://www.ncbi.nlm.nih.gov/books/NBK554838)

Once publications are selected for inclusion in a database, NLM does not review, evaluate, or judge the quality of individual articles and relies on the scientific publishing process to identify and address problems through published comments, corrections, and retractions (or, as in the case of preprints, withdrawal notices). The publisher is responsible for maintaining the currency of the scientific record and depositing all relevant updates to the appropriate NLM database.

NLM literature databases also archive and index articles, author manuscripts, and book chapters that may be from publications that have not yet undergone scientific review by NLM, are traditionally out of scope for the NLM collection, or have not met NLM’s standards for inclusion in a given database if a paper is deposited under:

- The [NIH Public Access Policy](https://publicaccess.nih.gov/) or a similar funder policy: NIH and other funders do not dictate where their funded authors may publish. Most records in the NLM literature databases have not been funded by the NIH or other agencies of the U.S. Federal Government.
- OR
- [The PMC COVID-19 Collection](https://www.ncbi.nlm.nih.gov/pmc/about/covid-19/): The articles deposited under this initiative – and the terms under which they are made available – are at the discretion of the publisher. To participate in this collaboration, a publisher must have journals in scope and eligible for inclusion the NLM Collection.

PMC and PubMed also include preprints reporting NIH-supported research in support of the [NIH Preprint Pilot](https://www.ncbi.nlm.nih.gov/pmc/about/nihpreprints/). As preprints are interim research products that have not been peer reviewed, readers should be aware that any aspect of the research, including the results and conclusions, may change as a result of peer review.

## Liability

For documents and software available from this server, the U.S. Government does not warrant or assume any legal liability or responsibility for the accuracy, completeness, or usefulness of any information, apparatus, product, or process disclosed.

## Endorsement

NLM does not endorse or recommend any commercial products, processes, or services. The views and opinions of authors expressed on NLM's Web sites do not necessarily state or reflect those of the U.S. Government, and they may not be used for advertising or product endorsement purposes.

## External Links

Some NLM Web pages may provide links to other Internet sites for the convenience of users. NLM is not responsible for the availability or content of these external sites, nor does NLM endorse, warrant, or guarantee the products, services, or information described or offered at these other Internet sites. Users cannot assume that the external sites will abide by the same [Privacy Policy](https://www.nlm.nih.gov/privacy.html) to which NLM adheres. It is the responsibility of the user to examine the copyright and licensing restrictions of linked pages and to secure all necessary permissions.

## Pop-Up Advertisements

When visiting our Web site, your Web browser may produce pop-up advertisements. These advertisements were most likely produced by other Web sites you visited or by third party software installed on your computer. The NLM does not endorse or recommend products or services for which you may view a pop-up advertisement on your computer screen while visiting our site.

## Medical Information and Advice

It is not the intention of NLM to provide specific medical advice but rather to provide users with information to better understand their health and their diagnosed disorders. Specific medical advice will not be provided, and NLM urges you to consult with a qualified physician for diagnosis and for answers to your personal questions.
'''


def build_disclaimer_page() -> str:
    return DISCLAIMER_TEXT


def build_welcome_page(data: dict, studies: list, n_labels: int = 0) -> str:
    return '\n'.join([
        '---',
        'title: Clinical Evidence Index',
        'subtitle: ADHD and binge-eating pharmacotherapy research',
        'slug: welcome',
        'layout: overview',
        'hide-nav-links: true',
        '---',
        '',
        '<CardGroup cols={2}>',
        '  <Card title="Browse" icon="fa-regular fa-folder-open" href="/browse">',
        '    By drug, topic, study design, dosing regimen and region',
        '  </Card>',
        '  <Card title="Regulatory" icon="fa-regular fa-file-prescription" href="/regulatory">',
        '    Approved US prescribing information',
        '  </Card>',
        '</CardGroup>',
        '',
        '<Callout intent="warning">',
        'Bibliographic index for research use — not medical advice. [Disclaimer](/disclaimer)',
        '</Callout>',
        '',
    ])


# --------------------------------------------------------------------------
# navigation
# --------------------------------------------------------------------------

def update_nav(data: dict, studies: list, designs: dict, topics: dict,
               regions: dict, countries: dict, regimens: dict, labels: dict):
    with open(DOCS_YML) as f:
        d = yaml.safe_load(f)

    d['title'] = 'Clinical Evidence Index'

    # keep the published instance honest about who owns the repo
    for inst in d.get('instances', []):
        gh = inst.get('edit-this-page', {}).get('github')
        if gh:
            gh['owner'] = 'saintus-create'
            gh['repo'] = 'family-614073'

    by_coll = defaultdict(list)
    for s in studies:
        by_coll[s['collection']].append(s)

    catalogue = [{
        'page': 'Browse the index',
        'path': 'docs/pages/browse.mdx',
        'icon': 'fa-regular fa-folder-open',
    }]

    coll_items = []
    for coll in data['collections']:
        if by_coll.get(coll['key']):
            coll_items.append({
                'page': truncate(coll['name']),
                'path': f'docs/pages/index/collection-{coll["key"]}.mdx',
                'icon': COLLECTION_ICON.get(coll['key'], 'fa-regular fa-folder'),
            })
    catalogue.append({'section': 'Collections', 'contents': coll_items, 'collapsed': True})

    design_items = [{
        'page': truncate(name),
        'path': f'docs/pages/index/design-{slugify(name)}.mdx',
        'icon': DESIGN_ICON.get(name, 'fa-regular fa-file-lines'),
    } for name in DESIGN_ORDER if designs.get(name)]
    catalogue.append({'section': 'Study designs', 'contents': design_items, 'collapsed': True})

    topic_items = [{
        'page': truncate(name),
        'path': f'docs/pages/index/topic-{slugify(name)}.mdx',
        'icon': TOPIC_ICON.get(name, 'fa-regular fa-tag'),
    } for name in sorted(topics)]
    catalogue.append({'section': 'Topics', 'contents': topic_items, 'collapsed': True})

    regimen_items = [{
        'page': truncate(name),
        'path': f'docs/pages/index/regimen-{slugify(name)}.mdx',
        'icon': REGIMEN_ICON.get(name, 'fa-regular fa-clock'),
    } for name in REGIMEN_ORDER if regimens.get(name)]
    catalogue.append({'section': 'Dosing regimens', 'contents': regimen_items,
                      'collapsed': True})

    # Regions nest their countries so the sidebar stays navigable at 45 countries.
    region_items = []
    for region in REGION_ORDER:
        if not regions.get(region):
            continue
        in_region = sorted({c for s in regions[region] for c in s['countries']
                            if COUNTRY_REGION_LOOKUP.get(c) == region})
        region_items.append({
            'section': region,
            'collapsed': True,
            'contents': [{
                'page': 'Overview',
                'path': f'docs/pages/index/region-{slugify(region)}.mdx',
                'icon': REGION_ICON.get(region, 'fa-regular fa-globe'),
            }] + [{
                'page': truncate(c),
                'path': f'docs/pages/index/country-{slugify(c)}.mdx',
                'icon': 'fa-regular fa-location-dot',
            } for c in in_region if countries.get(c)],
        })
    catalogue.append({'section': 'Regions & countries', 'contents': region_items,
                      'collapsed': True})

    if labels.get('labels'):
        catalogue.append({
            'section': 'Regulatory guidance',
            'collapsed': True,
            'contents': [{
                'page': 'Overview',
                'path': 'docs/pages/regulatory.mdx',
                'icon': 'fa-regular fa-scale-balanced',
            }] + [{
                'page': truncate(lab['name']),
                'path': f'docs/pages/labels/label-{lab["key"]}.mdx',
                'icon': 'fa-regular fa-file-prescription',
            } for lab in labels['labels']],
        })

    catalogue.append({
        'page': 'Disclaimer',
        'path': 'docs/pages/disclaimer.mdx',
        'icon': 'fa-regular fa-circle-info',
    })

    # Records, grouped by decade so no single section runs hundreds deep.
    by_decade = defaultdict(list)
    for s in studies:
        by_decade[(s['year'] // 10) * 10 if s['year'] else 0].append(s)
    record_sections = []
    for decade in sorted(by_decade, reverse=True):
        items = sorted(by_decade[decade], key=lambda x: (-(x['year'] or 0), x['title']))
        record_sections.append({
            'section': f'{decade}s' if decade else 'Undated',
            'collapsed': True,
            'contents': [{
                'page': truncate(s['title']),
                'path': f'docs/pages/studies/{study_slug(s)}.mdx',
                'icon': DESIGN_ICON.get(s['design'], 'fa-regular fa-file-lines'),
            } for s in items],
        })
    catalogue.append({'section': 'Records', 'contents': record_sections, 'collapsed': True})

    for tab in d['navigation']:
        if tab.get('tab') == 'home':
            tab['layout'] = [{
                'page': 'Home',
                'path': 'docs/pages/welcome.mdx',
                'slug': 'welcome',
            }]
        elif tab.get('tab') == 'evidence':
            tab['layout'] = catalogue

    ai = d.setdefault('ai-search', {})
    ai['system-prompt'] = (
        'You are a reference librarian for the Clinical Evidence Index, a bibliographic '
        'catalogue of PubMed records on ADHD and binge-eating pharmacotherapy '
        '(lisdexamfetamine, amphetamines, methylphenidate, atomoxetine and other '
        'non-stimulants).\n\n'
        'Grounding rules:\n'
        '- Answer only from the indexed records. If the index does not cover something, say '
        'so plainly and suggest a PubMed search instead of filling the gap from memory.\n'
        '- Cite every claim as: first author, journal, year, PMID. Link to the record page.\n'
        '- Never state a PMID, DOI, author or finding that is not in the indexed record. Do '
        'not reconstruct citations from memory; a wrong identifier is worse than no answer.\n\n'
        'Weighing evidence:\n'
        '- Report the study design with each finding and prefer meta-analyses, systematic '
        'reviews and randomized controlled trials over narrative reviews and case reports.\n'
        '- Separate findings replicated across several records from single-study results, and '
        'surface disagreement between records rather than averaging it away.\n'
        '- Note the studied population (children, adolescents, adults) and do not generalise '
        'a finding beyond it.\n'
        '- Abstracts alone rarely support causal claims; describe what was measured and in '
        'whom, and keep effect sizes in the units the abstract uses.\n'
        '- The index is a relevance-ranked sample of PubMed, not a systematic review, so do '
        'not present a tally of records as evidence of consensus.\n\n'
        'Geography: records carry the countries listed in author affiliations. When asked '
        'about a country or region, use those tags and say how many records support the '
        'answer. Coverage is concentrated in North America and Europe, so do not present '
        'the index as representative of worldwide practice.\n\n'
        'Dosing questions: separate the two sources sharply.\n'
        '- Study regimens (once daily, divided doses, extended release, titration) are '
        'tagged from abstracts and describe what a trial administered. Report them as study '
        'conditions, never as recommendations.\n'
        '- The regulatory pages carry approved US prescribing information from DailyMed. '
        'Quote those for approved dosing, and link the product label page.\n'
        '- Approved dosing, age limits and controlled-substance scheduling differ by '
        'country; the labels indexed here are US-only. Say so when a dosing question could '
        'be international.\n'
        '- Never synthesise a dose recommendation, extrapolate beyond the label, or advise '
        'on titration for an individual.\n\n'
        'Scope: this is a research index, not medical advice. State that briefly when a '
        'question turns clinical, then answer the bibliographic question fully. Do not '
        'recommend doses, compare products commercially, or advise on any individual case. '
        'For anything resembling a personal treatment decision, direct the reader to a '
        'qualified clinician and the full approved label.'
    )

    with open(DOCS_YML, 'w') as f:
        yaml.dump(d, f, sort_keys=False, default_flow_style=False, width=200,
                  allow_unicode=True)


def main():
    data = json.loads(STUDIES_JSON.read_text())
    studies = data['studies']
    labels = json.loads(LABELS_JSON.read_text()) if LABELS_JSON.exists() else {'labels': []}

    for directory in (STUDIES_DIR, INDEX_DIR, LABELS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        for old in directory.glob('*.mdx'):
            old.unlink()
    # legacy flat pages from earlier revisions
    for old in PAGES.glob('study-*.mdx'):
        old.unlink()
    for old in ('evidence-overview.mdx',):
        if (PAGES / old).exists():
            (PAGES / old).unlink()

    for s in studies:
        related = pick_related(s, studies)
        (STUDIES_DIR / f'{study_slug(s)}.mdx').write_text(build_study_page(s, related))

    by_coll = defaultdict(list)
    for s in studies:
        by_coll[s['collection']].append(s)
    for coll in data['collections']:
        items = by_coll.get(coll['key'])
        if items:
            (INDEX_DIR / f'collection-{coll["key"]}.mdx').write_text(
                build_collection_page(coll, items))

    designs = defaultdict(list)
    for s in studies:
        designs[s['design']].append(s)
    for name, items in designs.items():
        (INDEX_DIR / f'design-{slugify(name)}.mdx').write_text(build_design_page(name, items))

    topics = defaultdict(list)
    for s in studies:
        for t in s['topics']:
            topics[t].append(s)
    for name, items in topics.items():
        (INDEX_DIR / f'topic-{slugify(name)}.mdx').write_text(build_topic_page(name, items))

    regions = defaultdict(list)
    for s in studies:
        for r in s['regions']:
            regions[r].append(s)
    for name, items in regions.items():
        (INDEX_DIR / f'region-{slugify(name)}.mdx').write_text(
            build_region_page(name, items))

    countries = defaultdict(list)
    for s in studies:
        for c in s['countries']:
            countries[c].append(s)
    for name, items in countries.items():
        (INDEX_DIR / f'country-{slugify(name)}.mdx').write_text(
            build_country_page(name, items))

    regimens = defaultdict(list)
    for s in studies:
        for r in s['regimens']:
            regimens[r].append(s)
    for name, items in regimens.items():
        (INDEX_DIR / f'regimen-{slugify(name)}.mdx').write_text(
            build_regimen_page(name, items))

    if labels.get('labels'):
        (PAGES / 'regulatory.mdx').write_text(build_regulatory_overview(labels))
        for lab in labels['labels']:
            (LABELS_DIR / f'label-{lab["key"]}.mdx').write_text(build_label_page(lab))

    (PAGES / 'disclaimer.mdx').write_text(build_disclaimer_page())
    (PAGES / 'browse.mdx').write_text(build_browse_page(data, studies))
    (PAGES / 'welcome.mdx').write_text(
        build_welcome_page(data, studies, len(labels.get('labels', []))))

    update_nav(data, studies, designs, topics, regions, countries, regimens, labels)

    print(f'Generated {len(studies)} record pages, {len(by_coll)} collections, '
          f'{len(designs)} designs, {len(topics)} topics, {len(regions)} regions, '
          f'{len(countries)} countries, {len(regimens)} regimens, '
          f'{len(labels.get("labels", []))} labels.')


if __name__ == '__main__':
    main()
