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
DOCS_YML = FERN / 'docs.yml'
STUDIES_JSON = FERN / 'data' / 'studies.json'

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
                f'  <Card title={yaml_quote(truncate(r["title"], 72))} '
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
            f'  <Card title={yaml_quote(coll["name"])} '
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
    lines += ['', '  </Tab>', '  <Tab title="By decade">', '', '| Decade | Records |', '|---|---|']
    decades = Counter(f'{(y // 10) * 10}s' for y in years)
    for decade in sorted(decades):
        lines.append(f'| {decade} | {decades[decade]} |')
    lines += ['', '  </Tab>', '</Tabs>', '']

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


def build_welcome_page(data: dict, studies: list) -> str:
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
        '  <Card title="Safety & tolerability" icon="fa-regular fa-shield-halved" '
        'href="/topic-safety-tolerability">',
        '    Adverse events, cardiovascular and growth outcomes',
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

def update_nav(data: dict, studies: list, designs: dict, topics: dict):
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
        'Scope: this is a research index, not medical advice. State that briefly when a '
        'question turns clinical, then answer the bibliographic question fully. Do not '
        'recommend doses, compare products commercially, or advise on any individual case.'
    )

    with open(DOCS_YML, 'w') as f:
        yaml.dump(d, f, sort_keys=False, default_flow_style=False, width=200,
                  allow_unicode=True)


def main():
    data = json.loads(STUDIES_JSON.read_text())
    studies = data['studies']

    for directory in (STUDIES_DIR, INDEX_DIR):
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

    (PAGES / 'browse.mdx').write_text(build_browse_page(data, studies))
    (PAGES / 'welcome.mdx').write_text(build_welcome_page(data, studies))

    update_nav(data, studies, designs, topics)

    print(f'Generated {len(studies)} record pages, {len(by_coll)} collections, '
          f'{len(designs)} designs, {len(topics)} topics.')


if __name__ == '__main__':
    main()
