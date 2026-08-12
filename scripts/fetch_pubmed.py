#!/usr/bin/env python3
"""
Harvest real study records from PubMed E-utilities into fern/data/studies.json.

Every record in the catalogue originates from a live PubMed query, so each
entry's PMID, title, authors, journal, year, abstract and publication type are
whatever NCBI actually returns -- nothing is hand-written.

Usage:
    python3 scripts/fetch_pubmed.py            # refresh the catalogue
    python3 scripts/fetch_pubmed.py --verify   # only re-check existing PMIDs
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'fern' / 'data' / 'studies.json'

EUTILS = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
TOOL = 'clinical-evidence-index'
EMAIL = 'docs@example.org'

# Each query defines one drug-class collection in the catalogue. Filters keep
# results to human clinical literature with an abstract.
BASE_FILTER = '(humans[Filter] AND hasabstract)'

COLLECTIONS = [
    {
        'key': 'lisdexamfetamine',
        'name': 'Lisdexamfetamine',
        'query': '"lisdexamfetamine"[Title/Abstract]',
        'retmax': 70,
    },
    {
        'key': 'amphetamine',
        'name': 'Amphetamine & mixed amphetamine salts',
        'query': '("mixed amphetamine salts"[Title/Abstract] OR "Adderall"[Title/Abstract] '
                 'OR "dextroamphetamine"[Title/Abstract]) AND ADHD[Title/Abstract]',
        'retmax': 45,
    },
    {
        'key': 'methylphenidate',
        'name': 'Methylphenidate',
        'query': '("methylphenidate"[Title/Abstract] OR "dexmethylphenidate"[Title/Abstract]) '
                 'AND ADHD[Title/Abstract]',
        'retmax': 55,
    },
    {
        'key': 'atomoxetine',
        'name': 'Non-stimulants (atomoxetine, guanfacine, viloxazine)',
        'query': '("atomoxetine"[Title/Abstract] OR "guanfacine"[Title/Abstract] '
                 'OR "viloxazine"[Title/Abstract]) AND ADHD[Title/Abstract]',
        'retmax': 45,
    },
    {
        'key': 'comparative',
        'name': 'Comparative effectiveness & safety',
        'query': '(ADHD[Title/Abstract] AND (stimulant*[Title/Abstract] OR pharmacotherap*[Title/Abstract])) '
                 'AND (comparative[Title/Abstract] OR "network meta-analysis"[Title/Abstract] '
                 'OR "head-to-head"[Title/Abstract] OR safety[Title/Abstract])',
        'retmax': 45,
    },
    {
        'key': 'binge-eating',
        'name': 'Binge eating disorder',
        'query': '"binge eating"[Title/Abstract] AND (lisdexamfetamine[Title/Abstract] '
                 'OR pharmacotherap*[Title/Abstract] OR stimulant*[Title/Abstract])',
        'retmax': 35,
    },
    # Design-targeted passes. Relevance sort alone over-returns narrative
    # reviews, so these pull primary trial evidence explicitly.
    {
        'key': 'trials',
        'name': 'Randomized controlled trials',
        'query': '(ADHD[Title/Abstract] OR "binge eating"[Title/Abstract]) '
                 'AND (lisdexamfetamine[Title/Abstract] OR methylphenidate[Title/Abstract] '
                 'OR amphetamine[Title/Abstract] OR atomoxetine[Title/Abstract] '
                 'OR guanfacine[Title/Abstract] OR viloxazine[Title/Abstract]) '
                 'AND randomized controlled trial[Publication Type]',
        'retmax': 90,
    },
    {
        'key': 'pharmacokinetics',
        'name': 'Pharmacokinetics & dosing',
        'query': '(lisdexamfetamine[Title/Abstract] OR methylphenidate[Title/Abstract] '
                 'OR amphetamine[Title/Abstract] OR atomoxetine[Title/Abstract]) '
                 'AND (pharmacokinetic*[Title/Abstract] OR bioavailability[Title/Abstract] '
                 'OR "dose-response"[Title/Abstract] OR titration[Title/Abstract])',
        'retmax': 45,
    },
    {
        'key': 'long-term-safety',
        'name': 'Long-term & cardiovascular safety',
        'query': '(ADHD[Title/Abstract] AND (stimulant*[Title/Abstract] OR methylphenidate[Title/Abstract] '
                 'OR amphetamine[Title/Abstract] OR lisdexamfetamine[Title/Abstract])) '
                 'AND (cardiovascular[Title/Abstract] OR "blood pressure"[Title/Abstract] '
                 'OR growth[Title/Abstract] OR "long-term safety"[Title/Abstract] '
                 'OR "adverse events"[Title/Abstract] OR mortality[Title/Abstract])',
        'retmax': 55,
    },
]

# Study-design classification, checked in order. Driven by PubMed's own
# publication-type tags first, then abstract phrasing.
DESIGN_BY_PUBTYPE = [
    ('Meta-analysis', {'Meta-Analysis'}),
    ('Systematic review', {'Systematic Review'}),
    ('Randomized controlled trial', {'Randomized Controlled Trial'}),
    ('Clinical trial', {'Clinical Trial', 'Controlled Clinical Trial',
                        'Clinical Trial, Phase II', 'Clinical Trial, Phase III',
                        'Clinical Trial, Phase IV'}),
    ('Practice guideline', {'Practice Guideline', 'Guideline'}),
    ('Review', {'Review'}),
    ('Case report', {'Case Reports'}),
]

DESIGN_BY_TEXT = [
    ('Meta-analysis', r'\bmeta-?analys'),
    ('Systematic review', r'\bsystematic review'),
    ('Randomized controlled trial', r'\brandomi[sz]ed|\bdouble-?blind|\bplacebo-?controlled'),
    ('Cohort study', r'\bcohort\b|\blongitudinal\b|\bregistry\b|\bfollow-?up study'),
    ('Case-control study', r'\bcase-?control'),
    ('Cross-sectional study', r'\bcross-?sectional|\bsurvey\b|\bprevalence\b'),
    ('Pharmacokinetic study', r'\bpharmacokinetic|\bbioavailability|\bAUC\b|\bCmax\b'),
]

POPULATIONS = [
    ('Children', r'\bchildren\b|\bpediatric|\bpaediatric|\baged 6|\bschool-?age'),
    ('Adolescents', r'\badolescen|\bteenager|\byouth\b'),
    ('Adults', r'\badults?\b|\badulthood'),
    ('Older adults', r'\bolder adults?\b|\belderly\b|\bgeriatric'),
]

TOPICS = [
    ('Efficacy', r'\befficac|\bsymptom reduction|\bADHD-RS|\btreatment effect|\bresponse rate'),
    ('Safety & tolerability', r'\bsafety\b|\btolerabilit|\badverse event|\bside effect'),
    ('Cardiovascular', r'\bcardiovascular|\bblood pressure|\bheart rate|\bQT\b|\bcardiac'),
    ('Growth & development', r'\bgrowth\b|\bheight\b|\bweight\b|\bBMI\b|\bappetite'),
    ('Pharmacokinetics', r'\bpharmacokinetic|\bplasma concentration|\bhalf-?life|\bCmax\b'),
    ('Abuse liability', r'\babuse liabilit|\bmisuse\b|\bdiversion\b|\bdependence\b|\baddiction'),
    ('Cognition & function', r'\bexecutive function|\bcognitiv|\bworking memory|\bacademic'),
    ('Comorbidity', r'\bcomorbid|\bdepression\b|\banxiety\b|\boppositional|\bsubstance use'),
    ('Sleep', r'\bsleep\b|\binsomnia\b|\bcircadian'),
    ('Epidemiology & utilization', r'\bprescrib|\butilization|\bprevalence\b|\btrends\b|\bregistry'),
]


def eutils(endpoint: str, params: dict) -> str:
    params = {**params, 'tool': TOOL, 'email': EMAIL}
    url = f'{EUTILS}/{endpoint}?{urllib.parse.urlencode(params)}'
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as exc:  # transient NCBI throttling
            if attempt == 3:
                raise
            print(f'   retry {attempt + 1} after {exc}', file=sys.stderr)
            time.sleep(2 + attempt * 2)
    return ''


def esearch(query: str, retmax: int) -> list:
    full = f'({query}) AND {BASE_FILTER}'
    raw = eutils('esearch.fcgi', {
        'db': 'pubmed', 'term': full, 'retmax': retmax,
        'retmode': 'json', 'sort': 'relevance',
    })
    return json.loads(raw)['esearchresult'].get('idlist', [])


def text_of(node, path, default=''):
    found = node.find(path)
    if found is None:
        return default
    return ''.join(found.itertext()).strip() or default


def parse_article(art) -> dict:
    pmid = text_of(art, './MedlineCitation/PMID')
    if not pmid:
        return None

    title = text_of(art, './MedlineCitation/Article/ArticleTitle')
    title = re.sub(r'\s+', ' ', title).strip().rstrip('.')
    # PubMed brackets translated non-English titles: "[Foo]."
    translated = title.startswith('[') and title.endswith(']')
    if translated:
        title = title[1:-1].strip()
    if not title:
        return None

    # Abstract may be split into labelled sections.
    chunks = []
    for ab in art.findall('./MedlineCitation/Article/Abstract/AbstractText'):
        label = (ab.get('Label') or '').strip()
        body = ''.join(ab.itertext()).strip()
        if not body:
            continue
        chunks.append(f'**{label.title()}:** {body}' if label else body)
    abstract = '\n\n'.join(chunks)
    if not abstract:
        return None

    authors = []
    for a in art.findall('./MedlineCitation/Article/AuthorList/Author'):
        last = text_of(a, './LastName')
        initials = text_of(a, './Initials')
        collective = text_of(a, './CollectiveName')
        if last:
            authors.append(f'{last} {initials}'.strip())
        elif collective:
            authors.append(collective)

    journal = (text_of(art, './MedlineCitation/Article/Journal/ISOAbbreviation')
               or text_of(art, './MedlineCitation/Article/Journal/Title'))

    year = (text_of(art, './/JournalIssue/PubDate/Year')
            or text_of(art, './/JournalIssue/PubDate/MedlineDate')[:4]
            or text_of(art, './/ArticleDate/Year'))
    year = int(year) if year.isdigit() else None

    pubtypes = [''.join(p.itertext()).strip()
                for p in art.findall('./MedlineCitation/Article/PublicationTypeList/PublicationType')]

    doi = ''
    pmcid = ''
    for aid in art.findall('.//ArticleId'):
        idtype = aid.get('IdType')
        val = ''.join(aid.itertext()).strip()
        if idtype == 'doi' and not doi:
            doi = val
        elif idtype == 'pmc' and not pmcid:
            pmcid = val

    mesh = [''.join(m.itertext()).strip()
            for m in art.findall('.//MeshHeadingList/MeshHeading/DescriptorName')]

    language = text_of(art, './MedlineCitation/Article/Language', 'eng')

    haystack = f'{title} {abstract}'.lower()

    design = ''
    ptset = set(pubtypes)
    for name, tags in DESIGN_BY_PUBTYPE:
        if ptset & tags:
            design = name
            break
    if not design:
        for name, pattern in DESIGN_BY_TEXT:
            if re.search(pattern, haystack):
                design = name
                break
    design = design or 'Other'

    populations = [n for n, p in POPULATIONS if re.search(p, haystack)]
    topics = [n for n, p in TOPICS if re.search(p, haystack)]

    return {
        'pmid': pmid,
        'title': title,
        'title_translated': translated,
        'authors': authors,
        'journal': journal,
        'year': year,
        'language': language,
        'design': design,
        'publication_types': pubtypes,
        'populations': populations,
        'topics': topics,
        'mesh': mesh[:12],
        'doi': doi,
        'pmcid': pmcid,
        'abstract': abstract,
    }


def efetch(pmids: list) -> list:
    out = []
    for i in range(0, len(pmids), 100):
        batch = pmids[i:i + 100]
        raw = eutils('efetch.fcgi', {
            'db': 'pubmed', 'id': ','.join(batch), 'retmode': 'xml',
        })
        root = ET.fromstring(raw)
        for art in root.findall('.//PubmedArticle'):
            rec = parse_article(art)
            if rec:
                out.append(rec)
        time.sleep(0.4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true',
                    help='re-check PMIDs already in studies.json and exit')
    args = ap.parse_args()

    if args.verify:
        data = json.loads(OUT.read_text())
        pmids = [s['pmid'] for s in data['studies']]
        live = {r['pmid']: r for r in efetch(pmids)}
        bad = [p for p in pmids if p not in live]
        drift = [(s['pmid'], s['title'], live[s['pmid']]['title'])
                 for s in data['studies']
                 if s['pmid'] in live and s['title'] != live[s['pmid']]['title']]
        print(f'checked {len(pmids)} PMIDs: {len(pmids) - len(bad)} resolve, {len(bad)} missing')
        for p in bad:
            print('  MISSING', p)
        for pmid, ours, theirs in drift:
            print(f'  DRIFT {pmid}\n    ours:   {ours}\n    pubmed: {theirs}')
        return

    seen = {}
    collections = []
    for c in COLLECTIONS:
        print(f'-> {c["name"]}')
        ids = esearch(c['query'], c['retmax'])
        print(f'   {len(ids)} hits')
        records = efetch(ids)
        print(f'   {len(records)} with usable metadata')
        keys = []
        for r in records:
            if r['pmid'] not in seen:
                r['collection'] = c['key']
                seen[r['pmid']] = r
            keys.append(r['pmid'])
        collections.append({
            'key': c['key'],
            'name': c['name'],
            'query': f'({c["query"]}) AND {BASE_FILTER}',
            'pmids': keys,
        })
        time.sleep(0.5)

    studies = sorted(seen.values(), key=lambda s: (-(s['year'] or 0), s['title']))

    payload = {
        'generated': time.strftime('%Y-%m-%d'),
        'source': 'NCBI PubMed E-utilities',
        'note': 'Every record is fetched live from PubMed; no metadata is hand-entered.',
        'collections': collections,
        'studies': studies,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + '\n')
    print(f'\nwrote {len(studies)} verified studies to {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
