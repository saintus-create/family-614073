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
    {
        'key': 'dosing-regimens',
        'name': 'Dosing regimens & daily schedules',
        'query': '(ADHD[Title/Abstract] OR "binge eating"[Title/Abstract]) '
                 'AND (lisdexamfetamine[Title/Abstract] OR methylphenidate[Title/Abstract] '
                 'OR amphetamine[Title/Abstract] OR atomoxetine[Title/Abstract]) '
                 'AND ("once daily"[Title/Abstract] OR "twice daily"[Title/Abstract] '
                 'OR "divided doses"[Title/Abstract] OR "multiple dose"[Title/Abstract] '
                 'OR "extended release"[Title/Abstract] OR "immediate release"[Title/Abstract] '
                 'OR "dosing regimen"[Title/Abstract] OR "duration of effect"[Title/Abstract])',
        'retmax': 60,
    },
    {
        'key': 'international',
        'name': 'International & cross-national research',
        'query': '(ADHD[Title/Abstract] AND (medication[Title/Abstract] OR stimulant*[Title/Abstract] '
                 'OR pharmacotherap*[Title/Abstract])) '
                 'AND (international[Title/Abstract] OR cross-national[Title/Abstract] '
                 'OR multinational[Title/Abstract] OR "multicenter"[Title/Abstract] '
                 'OR Europe[Title/Abstract] OR Asia[Title/Abstract] OR "Latin America"[Title/Abstract] '
                 'OR Africa[Title/Abstract] OR Australia[Title/Abstract] OR Japan[Title/Abstract] '
                 'OR China[Title/Abstract] OR Brazil[Title/Abstract] OR Scandinavia[Title/Abstract] '
                 'OR "national registry"[Title/Abstract])',
        'retmax': 70,
    },
    {
        'key': 'guidelines',
        'name': 'Clinical guidelines & consensus statements',
        'query': '(ADHD[Title/Abstract] OR "binge eating"[Title/Abstract]) '
                 'AND (guideline*[Title/Abstract] OR "consensus statement"[Title/Abstract] '
                 'OR recommendation*[Title/Abstract] OR "standards of care"[Title/Abstract] '
                 'OR NICE[Title/Abstract] OR "practice parameter"[Title/Abstract]) '
                 'AND (treatment[Title/Abstract] OR medication[Title/Abstract] OR dos*[Title/Abstract])',
        'retmax': 55,
    },
    # Off-label prescribing is the coverage-authorization use case: the
    # evidence a provider must cite under Health & Safety Code 1367.21(a)(3)(C).
    {
        'key': 'off-label',
        'name': 'Off-label prescribing & indications',
        'query': '("off-label"[Title/Abstract] OR "off label"[Title/Abstract] '
                 'OR unlicensed[Title/Abstract]) '
                 'AND (ADHD[Title/Abstract] OR "attention deficit"[Title/Abstract] '
                 'OR stimulant*[Title/Abstract] OR methylphenidate[Title/Abstract] '
                 'OR lisdexamfetamine[Title/Abstract] OR amphetamine[Title/Abstract] '
                 'OR atomoxetine[Title/Abstract] OR guanfacine[Title/Abstract])',
        'retmax': 70,
    },
    {
        'key': 'adults',
        'name': 'Adult ADHD',
        'query': '(ADHD[Title/Abstract] OR "attention deficit"[Title/Abstract]) '
                 'AND (adult*[Title/Abstract] OR "late diagnosis"[Title/Abstract] '
                 'OR "undiagnosed"[Title/Abstract]) '
                 'AND (medication[Title/Abstract] OR stimulant*[Title/Abstract] '
                 'OR treatment[Title/Abstract])',
        'retmax': 60,
    },
    {
        'key': 'comorbidity-substance',
        'name': 'Substance use & misuse',
        'query': '(ADHD[Title/Abstract] AND (stimulant*[Title/Abstract] '
                 'OR methylphenidate[Title/Abstract] OR amphetamine[Title/Abstract] '
                 'OR lisdexamfetamine[Title/Abstract])) '
                 'AND ("substance use"[Title/Abstract] OR misuse[Title/Abstract] '
                 'OR diversion[Title/Abstract] OR addiction[Title/Abstract] '
                 'OR "abuse liability"[Title/Abstract] OR dependence[Title/Abstract])',
        'retmax': 55,
    },
    {
        'key': 'shortage-access',
        'name': 'Access, shortages & disparities',
        'query': '(ADHD[Title/Abstract] AND (medication[Title/Abstract] '
                 'OR stimulant*[Title/Abstract] OR prescri*[Title/Abstract])) '
                 'AND (shortage[Title/Abstract] OR access[Title/Abstract] '
                 'OR disparit*[Title/Abstract] OR equity[Title/Abstract] '
                 'OR insurance[Title/Abstract] OR "prior authorization"[Title/Abstract] '
                 'OR cost[Title/Abstract] OR adherence[Title/Abstract])',
        'retmax': 60,
    },
    # Region-targeted passes. A single "international" query skews to the
    # largest publishing countries, so each region is harvested explicitly.
    {
        'key': 'region-europe',
        'name': 'European research',
        'query': '(ADHD[Title/Abstract] AND (medication[Title/Abstract] '
                 'OR stimulant*[Title/Abstract] OR pharmacotherap*[Title/Abstract])) '
                 'AND (Europe[Title/Abstract] OR Sweden[Title/Abstract] '
                 'OR Denmark[Title/Abstract] OR Norway[Title/Abstract] '
                 'OR Finland[Title/Abstract] OR Iceland[Title/Abstract] '
                 'OR Netherlands[Title/Abstract] OR Germany[Title/Abstract] '
                 'OR France[Title/Abstract] OR Spain[Title/Abstract] '
                 'OR Italy[Title/Abstract] OR Poland[Title/Abstract] '
                 'OR "United Kingdom"[Title/Abstract] OR Scotland[Title/Abstract])',
        'retmax': 60,
    },
    {
        'key': 'region-asia',
        'name': 'Asian research',
        'query': '(ADHD[Title/Abstract] AND (medication[Title/Abstract] '
                 'OR stimulant*[Title/Abstract] OR pharmacotherap*[Title/Abstract])) '
                 'AND (Asia[Title/Abstract] OR China[Title/Abstract] '
                 'OR Japan[Title/Abstract] OR Korea[Title/Abstract] '
                 'OR Taiwan[Title/Abstract] OR India[Title/Abstract] '
                 'OR Singapore[Title/Abstract] OR Thailand[Title/Abstract] '
                 'OR Malaysia[Title/Abstract] OR Vietnam[Title/Abstract] '
                 'OR Indonesia[Title/Abstract] OR Hong Kong[Title/Abstract])',
        'retmax': 55,
    },
    {
        'key': 'region-global-south',
        'name': 'Latin America, Africa & Middle East research',
        'query': '(ADHD[Title/Abstract] AND (medication[Title/Abstract] '
                 'OR stimulant*[Title/Abstract] OR pharmacotherap*[Title/Abstract] '
                 'OR treatment[Title/Abstract])) '
                 'AND (Brazil[Title/Abstract] OR Mexico[Title/Abstract] '
                 'OR Chile[Title/Abstract] OR Argentina[Title/Abstract] '
                 'OR Colombia[Title/Abstract] OR Peru[Title/Abstract] '
                 'OR "Latin America"[Title/Abstract] OR Africa[Title/Abstract] '
                 'OR Nigeria[Title/Abstract] OR Kenya[Title/Abstract] '
                 'OR Egypt[Title/Abstract] OR "South Africa"[Title/Abstract] '
                 'OR Israel[Title/Abstract] OR Turkey[Title/Abstract] '
                 'OR Iran[Title/Abstract] OR "Saudi Arabia"[Title/Abstract])',
        'retmax': 55,
    },
    {
        'key': 'region-oceania',
        'name': 'Australia & New Zealand research',
        'query': '(ADHD[Title/Abstract] AND (medication[Title/Abstract] '
                 'OR stimulant*[Title/Abstract] OR pharmacotherap*[Title/Abstract] '
                 'OR prescri*[Title/Abstract])) '
                 'AND (Australia[Title/Abstract] OR "New Zealand"[Title/Abstract])',
        'retmax': 35,
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

# Dosing regimens, read off the abstract. Captures how often a dose is taken --
# the distinction between one daily dose and a divided/multiple daily schedule.
REGIMENS = [
    ('Once daily', r'\bonce[-\s]?daily\b|\bonce a day\b|\bo\.?d\.?\b(?![a-z])|\bq\.?d\.?\b|\bsingle daily dose'),
    ('Twice daily', r'\btwice[-\s]?daily\b|\btwice a day\b|\bb\.?i\.?d\.?\b|\btwo daily doses'),
    ('Three times daily', r'\bthree times (a |per )?day\b|\bt\.?i\.?d\.?\b|\bthrice daily'),
    ('Divided / multiple daily doses', r'\bdivided dose|\bmultiple[-\s]?dose|\bsplit[-\s]?dose|'
                                       r'\bmultiple daily\b|\btwice[-\s]?daily\b|\bthree times (a |per )?day\b|'
                                       r'\bb\.?i\.?d\.?\b|\bt\.?i\.?d\.?\b'),
    ('Titrated to effect', r'\btitrat|\bdose[-\s]?optimi[sz]|\bstepwise dos|\bup-?titrat|\bforced[-\s]?dose'),
    ('Single dose (study)', r'\bsingle[-\s]?dose\b|\bsingle oral dose\b'),
    ('Extended release', r'\bextended[-\s]?release\b|\bXR\b|\bER\b(?![a-z])|\bOROS\b|\bmodified[-\s]?release|'
                         r'\blong[-\s]?acting\b|\bprolonged[-\s]?release'),
    ('Immediate release', r'\bimmediate[-\s]?release\b|\bIR\b(?![a-z])|\bshort[-\s]?acting\b'),
]

# Country of the research, taken from author affiliations. PubMed affiliations
# are free text, so match on the trailing country name plus common variants.
COUNTRY_PATTERNS = [
    ('United States', r'\bUSA\b|\bU\.S\.A\b|\bUnited States\b|\bU\.S\.\b'),
    ('United Kingdom', r'\bUnited Kingdom\b|\bUK\b|\bEngland\b|\bScotland\b|\bWales\b|\bLondon\b'),
    ('Canada', r'\bCanada\b'),
    ('Germany', r'\bGermany\b|\bDeutschland\b'),
    ('Netherlands', r'\bNetherlands\b|\bHolland\b'),
    ('Sweden', r'\bSweden\b'),
    ('Denmark', r'\bDenmark\b'),
    ('Norway', r'\bNorway\b'),
    ('Finland', r'\bFinland\b'),
    ('Iceland', r'\bIceland\b'),
    ('Spain', r'\bSpain\b|\bEspaña\b'),
    ('Italy', r'\bItaly\b|\bItalia\b'),
    ('France', r'\bFrance\b'),
    ('Belgium', r'\bBelgium\b'),
    ('Switzerland', r'\bSwitzerland\b'),
    ('Austria', r'\bAustria\b'),
    ('Ireland', r'\bIreland\b'),
    ('Portugal', r'\bPortugal\b'),
    ('Poland', r'\bPoland\b'),
    ('Czech Republic', r'\bCzech\b'),
    ('Hungary', r'\bHungary\b'),
    ('Greece', r'\bGreece\b'),
    ('Turkey', r'\bTurkey\b|\bTürkiye\b'),
    ('Israel', r'\bIsrael\b'),
    ('Russia', r'\bRussia\b'),
    ('China', r'\bChina\b|\bBeijing\b|\bShanghai\b'),
    ('Taiwan', r'\bTaiwan\b'),
    ('Hong Kong', r'\bHong Kong\b'),
    ('Japan', r'\bJapan\b'),
    ('South Korea', r'\bKorea\b'),
    ('India', r'\bIndia\b'),
    ('Singapore', r'\bSingapore\b'),
    ('Thailand', r'\bThailand\b'),
    ('Malaysia', r'\bMalaysia\b'),
    ('Iran', r'\bIran\b'),
    ('Saudi Arabia', r'\bSaudi\b'),
    ('Egypt', r'\bEgypt\b'),
    ('South Africa', r'\bSouth Africa\b'),
    ('Nigeria', r'\bNigeria\b'),
    ('Australia', r'\bAustralia\b'),
    ('New Zealand', r'\bNew Zealand\b'),
    ('Brazil', r'\bBrazil\b|\bBrasil\b'),
    ('Argentina', r'\bArgentina\b'),
    ('Chile', r'\bChile\b'),
    ('Mexico', r'\bMexico\b|\bMéxico\b'),
    ('Colombia', r'\bColombia\b'),
]

# Rough UN-style region grouping so the index can report geographic spread.
COUNTRY_REGION = {
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
    affiliations = []
    for a in art.findall('./MedlineCitation/Article/AuthorList/Author'):
        last = text_of(a, './LastName')
        initials = text_of(a, './Initials')
        collective = text_of(a, './CollectiveName')
        if last:
            authors.append(f'{last} {initials}'.strip())
        elif collective:
            authors.append(collective)
        for aff in a.findall('./AffiliationInfo/Affiliation'):
            val = ''.join(aff.itertext()).strip()
            if val:
                affiliations.append(val)

    journal = (text_of(art, './MedlineCitation/Article/Journal/ISOAbbreviation')
               or text_of(art, './MedlineCitation/Article/Journal/Title'))

    year = (text_of(art, './/JournalIssue/PubDate/Year')
            or text_of(art, './/JournalIssue/PubDate/MedlineDate')[:4]
            or text_of(art, './/ArticleDate/Year'))
    year = int(year) if year.isdigit() else None

    volume = text_of(art, './/JournalIssue/Volume')
    issue = text_of(art, './/JournalIssue/Issue')
    pages = text_of(art, './MedlineCitation/Article/Pagination/MedlinePgn')
    medline_date = text_of(art, './/JournalIssue/PubDate/MedlineDate')
    month = text_of(art, './/JournalIssue/PubDate/Month')

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

    # Regimen matching is case-sensitive for the abbreviation-heavy patterns
    # (XR, IR, OROS), so run it against the original casing.
    regimen_text = f'{title} {abstract}'
    regimens = [n for n, p in REGIMENS if re.search(p, regimen_text, re.IGNORECASE if n not in
                ('Extended release', 'Immediate release') else 0)]

    # Dose strengths actually named in the abstract, e.g. "30 mg", "1.2 mg/kg".
    doses = sorted(set(
        re.findall(r'\b\d+(?:\.\d+)?\s?mg(?:/kg)?(?:/day)?\b', abstract, re.IGNORECASE)),
        key=lambda d: float(re.match(r'[\d.]+', d).group()))

    # Pull the conclusion and results out of structured abstracts so the site can
    # lead with what a study found instead of making people read the whole block.
    def section(*labels):
        for lab in labels:
            m = re.search(
                r'\*\*' + lab + r'[^:*]*:\*\*\s*(.+?)(?=\n\n\*\*|\Z)',
                abstract, re.IGNORECASE | re.DOTALL)
            if m:
                return re.sub(r'\s+', ' ', m.group(1)).strip()
        return ''

    def tidy(text: str) -> str:
        """Drop a trailing fragment left by a truncated source abstract.

        Some PubMed abstracts are cut off mid-sentence (often mid-number, e.g.
        "risk ratio 2."). Quoting that verbatim reads as a broken statistic, so
        trim back to the last sentence that actually terminates.
        """
        if not text:
            return text
        # a final "sentence" that ends on a dangling number or open bracket is
        # a truncation artefact, not a sentence
        if re.search(r'(?:\(|\b(?:ratio|CI|SD|SE|IQR|range)\s*[=:]?\s*)[\d.,\s]*\.\s*$',
                     text) or text.endswith('...'):
            sentences = re.findall(r'[^.!?]*[.!?]', text)
            while sentences:
                sentences.pop()
                cut = ''.join(sentences).strip()
                if not re.search(
                        r'(?:\(|\b(?:ratio|CI|SD|SE|IQR|range)\s*[=:]?\s*)[\d.,\s]*\.\s*$',
                        cut) and len(cut) > 80:
                    return cut
        return text

    conclusion = tidy(section('Conclusion', 'Interpretation', 'Conclusions and Relevance'))
    results = tidy(section('Result', 'Finding', 'Main Outcomes'))
    objective = section('Objective', 'Purpose', 'Aim', 'Importance', 'Background')

    # Unstructured abstracts: fall back to sentences that read like a conclusion.
    if not conclusion:
        m = re.search(
            r'((?:[A-Z][^.!?]*?\b(?:conclude|suggests?|indicates?|demonstrates?|'
            r'we found|these (?:results|findings|data))\b[^.!?]*[.!?])'
            r'(?:\s*[A-Z][^.!?]*[.!?])?)', abstract)
        if m:
            conclusion = tidy(re.sub(r'\s+', ' ', m.group(1)).strip())

    # Reported numbers worth surfacing next to a claim. Only whole statements
    # are kept -- a point estimate with its interval, or a standalone p-value.
    # Partial captures like "OR 1" or a bare "95% CI]" are worse than nothing
    # next to a clinical claim, so anything that does not match cleanly is dropped.
    stats = []
    num = r'-?\d+(?:\.\d+)?'
    ci = (r'(?:,?\s*(?:95%\s?(?:CI|confidence interval)\s*[,:]?\s*'
          r'\[?' + num + r'\s*(?:to|-|–|,)\s*' + num + r'\]?))')
    patterns = [
        # effect estimate followed by its confidence interval
        (r'\b(?:aOR|aHR|OR|HR|RR|IRR|SMD|MD|WMD)\s?[=:]?\s?' + num + ci, 'estimate'),
        # Cohen's d / Hedges' g
        (r"\b(?:Cohen'?s?\s?d|Hedges'?\s?g)\s?[=:]?\s?" + num, 'effect size'),
        # sample size, requires a plausible magnitude
        (r'\b[Nn]\s?=\s?(?:\d{3,}|\d{1,3}(?:,\d{3})+)\b', 'sample'),
        # p-value
        (r'\b[Pp]\s?[<=>]\s?0?\.\d+', 'p-value'),
    ]
    for pat, kind in patterns:
        for m in re.finditer(pat, abstract):
            val = re.sub(r'\s+', ' ', m.group(0)).strip().rstrip('.,;')
            if val.lower() not in [s['value'].lower() for s in stats]:
                stats.append({'kind': kind, 'value': val})
    stats = stats[:8]

    aff_text = ' ; '.join(affiliations)
    countries = [n for n, p in COUNTRY_PATTERNS if re.search(p, aff_text)]
    regions = sorted({COUNTRY_REGION[c] for c in countries if c in COUNTRY_REGION})

    return {
        'pmid': pmid,
        'title': title,
        'title_translated': translated,
        'authors': authors,
        'countries': countries,
        'regions': regions,
        'regimens': regimens,
        'doses': doses,
        'journal': journal,
        'year': year,
        'month': month,
        'volume': volume,
        'issue': issue,
        'pages': pages,
        'medline_date': medline_date,
        'language': language,
        'design': design,
        'publication_types': pubtypes,
        'populations': populations,
        'topics': topics,
        'mesh': mesh[:12],
        'doi': doi,
        'pmcid': pmcid,
        'objective': objective,
        'results': results,
        'conclusion': conclusion,
        'stats': stats,
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
