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


def citation(s: dict) -> str:
    """Vancouver-style reference line: first six authors, then et al."""
    names = s['authors']
    if not names:
        authors = 'No author listed.'
    elif len(names) <= 6:
        authors = ', '.join(names) + '.'
    else:
        authors = ', '.join(names[:6]) + ', et al.'
    bits = [authors]
    bits.append(f"{s['title']}.")
    tail = s['journal'] or 'n.p.'
    if s['year']:
        tail += f". {s['year']}"
    bits.append(tail + '.')
    if s['doi']:
        bits.append(f"doi:{s['doi']}.")
    bits.append(f"PMID:{s['pmid']}.")
    return mdx_safe(' '.join(bits))


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
    badges = [f'<Badge intent="{DESIGN_INTENT.get(s["design"], "note")}">{s["design"]}</Badge>']
    if s['year']:
        badges.append(f'<Badge intent="info" minimal>{s["year"]}</Badge>')
    for topic in s['topics'][:4]:
        badges.append(f'<Badge intent="note" minimal outlined>{mdx_safe(topic)}</Badge>')
    for regimen in s['regimens'][:3]:
        badges.append(f'<Badge intent="tip" minimal>{mdx_safe(regimen)}</Badge>')
    if s['pmcid']:
        badges.append('<Badge intent="success" minimal>Free full text</Badge>')

    lines = [
        '---',
        f'title: {yaml_quote(s["title"])}',
        f'subtitle: {yaml_quote(f"{s['journal']} · {s['year'] or 'n.d.'} · PMID {s['pmid']}")}',
        f'slug: {study_slug(s)}',
        '---',
        '',
        ' '.join(badges),
        '',
    ]

    if s['title_translated']:
        lines += [
            '<Callout intent="note">',
            f'Translated title. The article was published in {lang}; PubMed supplies the '
            'English rendering shown above.',
            '</Callout>',
            '',
        ]

    lines += [
        '## Record',
        '',
        '| Field | Value |',
        '|---|---|',
        f'| Authors | {esc_cell(author_line(s["authors"], 12))} |',
        f'| Journal | {esc_cell(s["journal"])} |',
        f'| Year | {s["year"] or "Not stated"} |',
        f'| Study design | {esc_cell(s["design"])} |',
        f'| Publication types | {esc_cell(", ".join(s["publication_types"]) or "Not stated")} |',
        f'| Population | {esc_cell(", ".join(s["populations"]) or "Not specified in abstract")} |',
        f'| Country | {esc_cell(", ".join(s["countries"]) or "Not stated in affiliations")} |',
        f'| Dosing regimen | {esc_cell(", ".join(s["regimens"]) or "Not stated in abstract")} |',
        f'| Doses named | {esc_cell(", ".join(s["doses"]) or "None named in abstract")} |',
        f'| Language | {esc_cell(lang)} |',
        f'| Sources | {source_links(s)} |',
        '',
        '## Abstract',
        '',
        mdx_safe(s['abstract']),
        '',
    ]

    if s['mesh']:
        terms = ' '.join(
            f'<Badge intent="note" minimal outlined>{mdx_safe(m)}</Badge>' for m in s['mesh'])
        lines += ['## MeSH terms', '', terms, '']

    lines += [
        '## Cite this record',
        '',
        '<Callout intent="info">',
        citation(s),
        '</Callout>',
        '',
    ]

    if related:
        lines += ['## Related records', '', '<CardGroup cols={2}>']
        for r in related:
            desc = mdx_safe(f"{r['journal']} · {r['year'] or 'n.d.'} · {r['design']}")
            lines.append(
                f'  <Card title={jsx_attr(truncate(r["title"], 72))} '
                f'icon="{DESIGN_ICON.get(r["design"], "fa-regular fa-file-lines")}" '
                f'href="/{study_slug(r)}">')
            lines.append(f'    {desc}')
            lines.append('  </Card>')
        lines += ['</CardGroup>', '']

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


def build_collection_page(coll: dict, studies: list) -> str:
    designs = Counter(s['design'] for s in studies)
    years = [s['year'] for s in studies if s['year']]
    lines = [
        '---',
        f'title: {yaml_quote(coll["name"])}',
        f'subtitle: {yaml_quote(f"{len(studies)} indexed records")}',
        f'slug: collection-{coll["key"]}',
        '---',
        '',
        '<Callout intent="info">',
        f'**PubMed query.** All {len(studies)} records in this collection were retrieved with:',
        '',
        '```',
        coll['query'],
        '```',
        '</Callout>',
        '',
        '## At a glance',
        '',
        '| Metric | Value |',
        '|---|---|',
        f'| Records | {len(studies)} |',
        f'| Publication years | {min(years)}–{max(years)} |' if years else '| Publication years | n/a |',
        f'| Controlled trials | {designs["Randomized controlled trial"] + designs["Clinical trial"]} |',
        f'| Evidence syntheses | {designs["Meta-analysis"] + designs["Systematic review"]} |',
        f'| Free full text | {sum(1 for s in studies if s["pmcid"])} |',
        '',
        '## Records',
        '',
    ]
    lines += study_table(studies)
    lines.append('')
    return '\n'.join(lines)


def build_design_page(design: str, studies: list) -> str:
    lines = [
        '---',
        f'title: {yaml_quote(design)}',
        f'subtitle: {yaml_quote(f"{len(studies)} records with this study design")}',
        f'slug: design-{slugify(design)}',
        '---',
        '',
        f'<Badge intent="{DESIGN_INTENT.get(design, "note")}">{design}</Badge>',
        '',
        'Design is taken from the publication types PubMed assigns to each record, '
        'falling back to abstract wording when no design tag is present.',
        '',
    ]
    lines += study_table(studies)
    lines.append('')
    return '\n'.join(lines)


def build_topic_page(topic: str, studies: list) -> str:
    lines = [
        '---',
        f'title: {yaml_quote(topic)}',
        f'subtitle: {yaml_quote(f"{len(studies)} records tagged {topic.lower()}")}',
        f'slug: topic-{slugify(topic)}',
        '---',
        '',
        'Topic tags are derived from each abstract, so a record can appear under more than '
        'one topic.',
        '',
    ]
    lines += study_table(studies)
    lines.append('')
    return '\n'.join(lines)


def build_region_page(region: str, studies: list) -> str:
    countries = Counter(c for s in studies for c in s['countries']
                        if s['regions'] and region in s['regions'])
    lines = [
        '---',
        f'title: {yaml_quote(region)}',
        f'subtitle: {yaml_quote(f"{len(studies)} records with authors based in {region}")}',
        f'slug: region-{slugify(region)}',
        '---',
        '',
        'Location is taken from author affiliations on the PubMed record, so a '
        'multinational collaboration appears under every region it involves.',
        '',
        '## Countries represented',
        '',
        '| Country | Records |',
        '|---|---|',
    ]
    for country, n in countries.most_common():
        lines.append(f'| [{country}](/country-{slugify(country)}) | {n} |')
    lines += ['', '## Records', '']
    lines += study_table(studies)
    lines.append('')
    return '\n'.join(lines)


def build_country_page(country: str, studies: list) -> str:
    lines = [
        '---',
        f'title: {yaml_quote(country)}',
        f'subtitle: {yaml_quote(f"{len(studies)} records with authors based in {country}")}',
        f'slug: country-{slugify(country)}',
        '---',
        '',
    ]
    lines += study_table(studies)
    lines.append('')
    return '\n'.join(lines)


def build_regimen_page(regimen: str, studies: list) -> str:
    doses = Counter(d.lower().replace(' ', '') for s in studies for d in s['doses'])
    lines = [
        '---',
        f'title: {yaml_quote(regimen)}',
        f'subtitle: {yaml_quote(f"{len(studies)} records describing this regimen")}',
        f'slug: regimen-{slugify(regimen)}',
        '---',
        '',
        '<Callout intent="warning">',
        'Regimens are detected from abstract wording, which reflects what each study '
        'administered under trial conditions. These are not dosing recommendations. '
        'Approved dosing is on the [regulatory guidance](/regulatory) pages.',
        '</Callout>',
        '',
    ]
    if doses:
        top = ', '.join(f'`{d}`' for d, _ in doses.most_common(12))
        lines += ['**Dose strengths named in these abstracts:** ' + top, '']
    lines += study_table(studies)
    lines.append('')
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
        'Reference material, not medical advice. These pages reproduce approved US '
        'prescribing information as published in DailyMed. Labelling, approved '
        'indications, age limits and controlled-substance scheduling differ by country '
        '— outside the US, consult the applicable national regulator. Always read the '
        'current full label before any clinical decision.',
        '</Callout>',
        '',
        f'Source: {labels["source"]}. Retrieved {labels["generated"]}.',
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
    lines += [
        '',
        '<Callout intent="note">',
        'International note: the index catalogues research from 45 countries, but the '
        'labels below are US-specific. Lisdexamfetamine, for example, is marketed as '
        'Vyvanse in the US and Elvanse in much of Europe, with differing approved '
        'populations. See [research by region](/browse) for the evidence base outside '
        'the US.',
        '</Callout>',
        '',
    ]
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

    lines += [
        '<Callout intent="warning">',
        'Reproduced from the approved US label; sections are abridged for indexing. '
        f'Read the [complete current label]({lab["url"]}) before any clinical use. '
        'Requirements differ outside the United States.',
        '</Callout>',
        '',
    ]
    return '\n'.join(lines)


def build_browse_page(data: dict, studies: list) -> str:
    by_coll = defaultdict(list)
    for s in studies:
        by_coll[s['collection']].append(s)
    designs = Counter(s['design'] for s in studies)
    topics = Counter(t for s in studies for t in s['topics'])
    years = [s['year'] for s in studies if s['year']]

    lines = [
        '---',
        'title: Browse the index',
        f'subtitle: {yaml_quote(f"{len(studies)} PubMed records across {len(data['collections'])} collections")}',
        'slug: browse',
        '---',
        '',
        '<Callout intent="success">',
        f'Every record is fetched live from the NCBI PubMed E-utilities API '
        f'(catalogue built {data["generated"]}). Titles, authors, journals, abstracts and '
        'identifiers are reproduced as PubMed returns them.',
        '</Callout>',
        '',
        '## Collections',
        '',
        '<CardGroup cols={3}>',
    ]
    for coll in data['collections']:
        items = by_coll.get(coll['key'], [])
        if not items:
            continue
        lines.append(
            f'  <Card title={jsx_attr(coll["name"])} '
            f'icon="{COLLECTION_ICON.get(coll["key"], "fa-regular fa-folder")}" '
            f'href="/collection-{coll["key"]}">')
        lines.append(f'    {len(items)} records')
        lines.append('  </Card>')
    lines += ['</CardGroup>', '']

    lines += [
        '## Holdings',
        '',
        '<Tabs>',
        '  <Tab title="By study design">',
        '',
        '| Design | Records |',
        '|---|---|',
    ]
    for design in DESIGN_ORDER:
        if designs.get(design):
            lines.append(f'| [{design}](/design-{slugify(design)}) | {designs[design]} |')
    lines += ['', '  </Tab>', '  <Tab title="By topic">', '', '| Topic | Records |', '|---|---|']
    for topic, n in topics.most_common():
        lines.append(f'| [{topic}](/topic-{slugify(topic)}) | {n} |')
    lines += ['', '  </Tab>', '  <Tab title="By region">', '', '| Region | Records |', '|---|---|']
    regions = Counter(r for s in studies for r in s['regions'])
    for region in REGION_ORDER:
        if regions.get(region):
            lines.append(f'| [{region}](/region-{slugify(region)}) | {regions[region]} |')
    lines += ['', '  </Tab>', '  <Tab title="By regimen">', '',
              '| Dosing regimen | Records |', '|---|---|']
    regimens = Counter(r for s in studies for r in s['regimens'])
    for regimen in REGIMEN_ORDER:
        if regimens.get(regimen):
            lines.append(f'| [{regimen}](/regimen-{slugify(regimen)}) | {regimens[regimen]} |')
    lines += ['', '  </Tab>', '  <Tab title="By decade">', '', '| Decade | Records |', '|---|---|']
    decades = Counter(f'{(y // 10) * 10}s' for y in years)
    for decade in sorted(decades):
        lines.append(f'| {decade} | {decades[decade]} |')
    lines += ['', '  </Tab>', '</Tabs>', '']

    countries = Counter(c for s in studies for c in s['countries'])
    lines += [
        '## Geographic coverage',
        '',
        f'Author affiliations place these records across **{len(countries)} countries**. '
        'Coverage is uneven — the literature itself is concentrated in North America and '
        'Europe, and this index inherits that skew.',
        '',
        '| Country | Records |',
        '|---|---|',
    ]
    for country, n in countries.most_common(15):
        lines.append(f'| [{country}](/country-{slugify(country)}) | {n} |')
    lines.append('')

    lines += [
        '## How this index is built',
        '',
        '<Steps>',
        '  <Step title="Query PubMed">',
        '    Each collection is one E-utilities `esearch` query, filtered to human studies '
        'that have an abstract. The exact query string is printed on every collection page.',
        '  </Step>',
        '  <Step title="Fetch full records">',
        '    Matching PMIDs are retrieved with `efetch` in MEDLINE XML. Titles, authors, '
        'journal, year, abstract, MeSH headings, DOI and PMCID all come from that response.',
        '  </Step>',
        '  <Step title="Classify">',
        '    Study design comes from PubMed publication types, with an abstract-text fallback. '
        'Topic and population tags are matched against the abstract.',
        '  </Step>',
        '  <Step title="Render">',
        '    One page per record, plus the collection, design and topic indexes. Re-running '
        'the generator reproduces the site exactly.',
        '  </Step>',
        '</Steps>',
        '',
        '## Coverage and limits',
        '',
        '<AccordionGroup>',
        '  <Accordion title="What this index is">',
        '    A clearing house of published literature on ADHD and binge-eating '
        'pharmacotherapy. It points to primary sources; it does not summarise them into '
        'clinical recommendations.',
        '  </Accordion>',
        '  <Accordion title="What it is not">',
        '    Not a systematic review. Collections are relevance-ranked PubMed queries capped '
        'at a fixed number of records, so the index is a sample of the literature, not a '
        'complete or unbiased census of it. Absence from this index means nothing about a '
        "study's quality.",
        '  </Accordion>',
        '  <Accordion title="Known gaps">',
        '    Records without an abstract are excluded, which skews away from older articles, '
        'letters and conference material. Non-English records appear only when PubMed supplies '
        'a translated title. Grey literature, trial registries and unpublished results are '
        'out of scope.',
        '  </Accordion>',
        '  <Accordion title="Verifying the catalogue">',
        '    `python3 scripts/fetch_pubmed.py --verify` re-queries every PMID in the dataset '
        'and reports any that no longer resolve or whose title has drifted from the stored '
        'copy.',
        '  </Accordion>',
        '</AccordionGroup>',
        '',
    ]
    return '\n'.join(lines)


def build_welcome_page(data: dict, studies: list, n_labels: int = 0) -> str:
    years = [s['year'] for s in studies if s['year']]
    designs = Counter(s['design'] for s in studies)
    trials = designs['Randomized controlled trial'] + designs['Clinical trial']
    synth = designs['Meta-analysis'] + designs['Systematic review']
    return '\n'.join([
        '---',
        'title: Clinical Evidence Index',
        'subtitle: A PubMed-sourced clearing house for ADHD and binge-eating pharmacotherapy research',
        'slug: welcome',
        'layout: overview',
        'hide-nav-links: true',
        '---',
        '',
        '<Callout intent="success">',
        f'{len(studies)} records · {min(years)}–{max(years)} · every entry verified against '
        'the NCBI PubMed API',
        '</Callout>',
        '',
        '<CardGroup cols={2}>',
        '  <Card title="Browse the index" icon="fa-regular fa-folder-open" href="/browse">',
        '    Collections, study designs, topics and the method behind the catalogue',
        '  </Card>',
        '  <Card title="Randomized controlled trials" icon="fa-regular fa-flask" '
        'href="/design-randomized-controlled-trial">',
        f'    {designs["Randomized controlled trial"]} controlled trials indexed',
        '  </Card>',
        '  <Card title="Evidence syntheses" icon="fa-regular fa-layer-group" '
        'href="/design-meta-analysis">',
        f'    {synth} meta-analyses and systematic reviews',
        '  </Card>',
        '  <Card title="Regulatory guidance" icon="fa-regular fa-file-prescription" '
        'href="/regulatory">',
        '    Approved US dosing, scheduling and boxed warnings',
        '  </Card>',
        '</CardGroup>',
        '',
        '## Holdings',
        '',
        '| | |',
        '|---|---|',
        f'| Records indexed | {len(studies)} |',
        f'| Collections | {len(data["collections"])} |',
        f'| Controlled trials | {trials} |',
        f'| Evidence syntheses | {synth} |',
        f'| Free full text available | {sum(1 for s in studies if s["pmcid"])} |',
        f'| Countries represented | {len({c for s in studies for c in s["countries"]})} |',
        f'| Products with approved labelling | {n_labels} |',
        f'| Catalogue built | {data["generated"]} |',
        '',
        '<Callout intent="warning">',
        'This is a bibliographic index for research use. It reproduces published abstracts and '
        'does not interpret them, rank treatments, or constitute medical advice. Inclusion here '
        'is not endorsement of a study\'s conclusions, and the collections are relevance-ranked '
        'samples rather than exhaustive reviews. Consult a qualified clinician for care '
        'decisions.',
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
