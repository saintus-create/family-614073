#!/usr/bin/env python3
"""Harvest Drugs@FDA approval history into fern/data/fda.json.

Source: openFDA drug/drugsfda endpoint (public domain US Government data).
Captures every application, its products/strengths, and the full submission
history including original approvals, efficacy supplements and labelling
revisions, with links to the FDA-hosted review documents.
"""
import json
import pathlib
import time
import urllib.parse
import urllib.request

API = 'https://api.fda.gov/drug/drugsfda.json'
OUT = pathlib.Path(__file__).resolve().parent.parent / 'fern' / 'data' / 'fda.json'

# active-ingredient strings as they appear in Drugs@FDA
INGREDIENTS = [
    ('lisdexamfetamine', 'Lisdexamfetamine dimesylate', 'LISDEXAMFETAMINE DIMESYLATE'),
    ('amphetamine', 'Amphetamine (mixed salts)', 'AMPHETAMINE ASPARTATE'),
    ('dextroamphetamine', 'Dextroamphetamine', 'DEXTROAMPHETAMINE SULFATE'),
    ('methylphenidate', 'Methylphenidate', 'METHYLPHENIDATE HYDROCHLORIDE'),
    ('dexmethylphenidate', 'Dexmethylphenidate', 'DEXMETHYLPHENIDATE HYDROCHLORIDE'),
    ('atomoxetine', 'Atomoxetine', 'ATOMOXETINE HYDROCHLORIDE'),
    ('guanfacine', 'Guanfacine', 'GUANFACINE HYDROCHLORIDE'),
    ('viloxazine', 'Viloxazine', 'VILOXAZINE HYDROCHLORIDE'),
    ('clonidine', 'Clonidine', 'CLONIDINE HYDROCHLORIDE'),
]

# Submission classes worth surfacing as scientific events rather than admin churn.
NOTABLE = {
    'Efficacy', 'Type 1 - New Molecular Entity', 'Type 2 - New Active Ingredient',
    'Type 3 - New Dosage Form', 'Type 4 - New Combination',
    'Type 5 - New Formulation or New Manufacturer',
    'Type 6 - New Indication', 'Type 7 - Drug Already Marketed without Approved NDA',
    'Type 8 - Partial Rx to OTC Switch', 'Labeling', 'Manufacturing (CMC)',
    'REMS', 'Pediatric',
}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as exc:
            if i == tries - 1:
                print(f'    failed: {exc}')
                return None
            time.sleep(2 * (i + 1))
    return None


def fetch_ingredient(name):
    q = urllib.parse.quote(f'products.active_ingredients.name:"{name}"')
    results, skip = [], 0
    while True:
        data = get(f'{API}?search={q}&limit=100&skip={skip}')
        if not data or not data.get('results'):
            break
        results += data['results']
        total = data.get('meta', {}).get('results', {}).get('total', 0)
        skip += 100
        if skip >= total or skip >= 500:
            break
        time.sleep(0.3)
    return results


def clean_strength(s):
    # Drugs@FDA appends Federal Register notes into the strength field
    return (s or '').split('**')[0].strip().rstrip(',').strip()


def main():
    out = []
    for key, label, ingredient in INGREDIENTS:
        print(f'{label} …')
        apps = fetch_ingredient(ingredient)
        records = []
        for app in apps:
            products = []
            for p in app.get('products') or []:
                products.append({
                    'brand': p.get('brand_name'),
                    'form': p.get('dosage_form'),
                    'route': p.get('route'),
                    'status': p.get('marketing_status'),
                    'strengths': sorted({clean_strength(a.get('strength'))
                                         for a in p.get('active_ingredients') or []}),
                })

            subs = []
            for s in app.get('submissions') or []:
                cls = s.get('submission_class_code_description') or ''
                docs = []
                for d in s.get('application_docs') or []:
                    url = (d.get('url') or '').split(',')[0].strip()
                    if url.startswith('http'):
                        docs.append({'type': d.get('type'), 'url': url,
                                     'date': d.get('date')})
                subs.append({
                    'type': s.get('submission_type'),
                    'number': s.get('submission_number'),
                    'status': s.get('submission_status'),
                    'date': s.get('submission_status_date'),
                    'category': cls,
                    'review_priority': s.get('review_priority'),
                    'notable': cls in NOTABLE or s.get('submission_type') == 'ORIG',
                    'docs': docs,
                })
            subs.sort(key=lambda x: x['date'] or '', reverse=True)

            orig = [s for s in subs if s['type'] == 'ORIG']
            records.append({
                'application': app.get('application_number'),
                'sponsor': app.get('sponsor_name'),
                'brands': sorted({p['brand'] for p in products if p['brand']}),
                'products': products,
                'submissions': subs,
                'first_approval': min((s['date'] for s in orig if s['date']),
                                      default=None),
                'latest_action': subs[0]['date'] if subs else None,
                'url': 'https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm'
                       f'?event=overview.process&ApplNo='
                       f'{(app.get("application_number") or "").lstrip("ANDBLA")}',
            })

        # New Drug Applications first, then generics, newest approval first
        records.sort(key=lambda r: (not (r['application'] or '').startswith('NDA'),
                                    r['first_approval'] or '0'), reverse=False)
        nda = [r for r in records if (r['application'] or '').startswith('NDA')]
        anda = [r for r in records if not (r['application'] or '').startswith('NDA')]
        nda.sort(key=lambda r: r['first_approval'] or '9', reverse=False)

        out.append({
            'key': key,
            'name': label,
            'ingredient': ingredient,
            'applications': nda,
            'generic_count': len(anda),
            'generic_sponsors': sorted({r['sponsor'] for r in anda if r['sponsor']}),
        })
        print(f'  {len(nda)} NDA/BLA, {len(anda)} generic applications')
        time.sleep(0.3)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'drugs': out}, indent=1))
    total_subs = sum(len(a['submissions']) for d in out for a in d['applications'])
    print(f'\nWrote {OUT} — {len(out)} drugs, '
          f'{sum(len(d["applications"]) for d in out)} applications, '
          f'{total_subs} submissions')


if __name__ == '__main__':
    main()
