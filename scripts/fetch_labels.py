#!/usr/bin/env python3
"""
Harvest approved-labelling guidance from DailyMed (NLM's Structured Product
Label archive) into fern/data/labels.json.

DailyMed publishes the FDA-approved prescribing information for every marketed
US product as HL7 SPL XML. This script pulls the current label for each drug in
the index and keeps the sections that describe regulated use -- indications,
dosage and administration, boxed warning, contraindications, controlled-substance
scheduling and specific populations.

Nothing here is authored: every sentence is the approved label text as published.

Usage:
    python3 scripts/fetch_labels.py
"""

import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'fern' / 'data' / 'labels.json'

BASE = 'https://dailymed.nlm.nih.gov/dailymed/services/v2'
NS = {'v3': 'urn:hl7-org:v3'}

# One entry per active ingredient tracked by the index.
DRUGS = [
    {'key': 'lisdexamfetamine', 'name': 'Lisdexamfetamine dimesylate',
     'query': 'lisdexamfetamine', 'brands': 'Vyvanse, Elvanse (EU/UK)'},
    {'key': 'amphetamine', 'name': 'Mixed amphetamine salts',
     'query': 'dextroamphetamine saccharate', 'brands': 'Adderall, Adderall XR, Mydayis'},
    {'key': 'methylphenidate', 'name': 'Methylphenidate hydrochloride',
     'query': 'methylphenidate hydrochloride', 'brands': 'Ritalin, Concerta, Equasym, Medikinet'},
    {'key': 'dexmethylphenidate', 'name': 'Dexmethylphenidate hydrochloride',
     'query': 'dexmethylphenidate', 'brands': 'Focalin, Focalin XR'},
    {'key': 'atomoxetine', 'name': 'Atomoxetine hydrochloride',
     'query': 'atomoxetine', 'brands': 'Strattera'},
    {'key': 'guanfacine', 'name': 'Guanfacine (extended release)',
     'query': 'guanfacine', 'brands': 'Intuniv'},
    {'key': 'viloxazine', 'name': 'Viloxazine (extended release)',
     'query': 'viloxazine', 'brands': 'Qelbree'},
]

# SPL section titles worth surfacing, mapped to the label they get on the site.
WANTED = [
    (r'^WARNING[: ]|BOXED WARNING', 'Boxed warning'),
    (r'^1 INDICATIONS AND USAGE|^INDICATIONS AND USAGE', 'Indications and usage'),
    (r'^2 DOSAGE AND ADMINISTRATION|^DOSAGE AND ADMINISTRATION', 'Dosage and administration'),
    (r'^2\.\d+ ', 'Dosage detail'),
    (r'^3 DOSAGE FORMS AND STRENGTHS', 'Dosage forms and strengths'),
    (r'^4 CONTRAINDICATIONS', 'Contraindications'),
    (r'^8\.1 Pregnancy', 'Pregnancy'),
    (r'^8\.2 Lactation', 'Lactation'),
    (r'^8\.4 Pediatric Use', 'Pediatric use'),
    (r'^8\.5 Geriatric Use', 'Geriatric use'),
    (r'^9\.1 Controlled Substance', 'Controlled substance'),
    (r'^9\.2 Abuse', 'Abuse'),
    (r'^9\.3 Dependence', 'Dependence'),
]


def get(url: str) -> str:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 + attempt * 2)
    return ''


def clean(text: str) -> str:
    text = re.sub(r'\s+', ' ', text or '').strip()
    return text


def section_text(sec) -> str:
    """Flatten an SPL section body, keeping list items as separate lines."""
    parts = []
    for node in sec:
        tag = node.tag.split('}')[-1]
        if tag in ('title', 'component', 'id', 'code', 'effectiveTime'):
            continue
        if tag == 'text':
            for child in node.iter():
                ctag = child.tag.split('}')[-1]
                if ctag == 'item':
                    t = clean(''.join(child.itertext()))
                    if t:
                        parts.append(f'- {t}')
            if not parts:
                t = clean(''.join(node.itertext()))
                if t:
                    parts.append(t)
            else:
                # keep any leading paragraph that sits before the list
                lead = clean(''.join(
                    c.text or '' for c in node if c.tag.split('}')[-1] == 'paragraph'))
                if lead:
                    parts.insert(0, lead)
    return '\n'.join(parts).strip()


def find_label(drug: dict) -> tuple:
    """Pick the richest current SPL for the ingredient.

    Products are labelled in two formats: the modern Physician Labeling Rule
    layout with numbered sections, and an older free-form one that collapses
    everything into a handful of blocks. Newest-first alone can land on a sparse
    old-format label, so score the most recent candidates by how many wanted
    sections they actually yield and keep the best.
    """
    url = (f'{BASE}/spls.json?drug_name={urllib.parse.quote(drug["query"])}'
           f'&pagesize=25')
    rows = json.loads(get(url)).get('data', [])
    if not rows:
        return None, []

    def pub_time(r):
        try:
            return time.strptime(r.get('published_date', ''), '%b %d, %Y')
        except Exception:
            return time.gmtime(0)

    rows.sort(key=pub_time, reverse=True)

    best_row, best_sections = None, []
    for row in rows[:6]:
        try:
            sections = parse_spl(row['setid'])
        except Exception:
            continue
        if len(sections) > len(best_sections):
            best_row, best_sections = row, sections
        if len(best_sections) >= 12:  # rich enough, stop paying for more fetches
            break
        time.sleep(0.3)
    return best_row, best_sections


def parse_spl(setid: str) -> list:
    xml = get(f'{BASE}/spls/{setid}.xml')
    root = ET.fromstring(xml)
    out = []
    for sec in root.findall('.//v3:section', NS):
        title_el = sec.find('./v3:title', NS)
        if title_el is None:
            continue
        title = clean(''.join(title_el.itertext()))
        kind = None
        for pattern, label in WANTED:
            if re.search(pattern, title, re.IGNORECASE):
                kind = label
                break
        if not kind:
            continue
        body = section_text(sec)
        if not body or len(body) < 40:
            continue
        out.append({'kind': kind, 'title': title, 'text': body[:6000]})
    # de-duplicate by title, keeping first occurrence
    seen = set()
    deduped = []
    for s in out:
        if s['title'] in seen:
            continue
        seen.add(s['title'])
        deduped.append(s)
    return deduped


def main():
    labels = []
    for drug in DRUGS:
        print(f'-> {drug["name"]}')
        try:
            row, sections = find_label(drug)
            if not row:
                print('   no SPL found')
                continue
            print(f'   {len(sections)} sections from SPL {row["setid"][:8]} '
                  f'({row.get("published_date")})')
            labels.append({
                'key': drug['key'],
                'name': drug['name'],
                'brands': drug['brands'],
                'spl_title': clean(row.get('title', '')),
                'setid': row['setid'],
                'published': row.get('published_date', ''),
                'url': f'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={row["setid"]}',
                'sections': sections,
            })
        except Exception as exc:
            print(f'   failed: {exc}')
        time.sleep(0.6)

    payload = {
        'generated': time.strftime('%Y-%m-%d'),
        'source': 'DailyMed (U.S. National Library of Medicine) Structured Product Labels',
        'note': 'Approved US prescribing information, reproduced verbatim. '
                'Labelling differs by country.',
        'labels': labels,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + '\n')
    print(f'\nwrote {len(labels)} labels to {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
