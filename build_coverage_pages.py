#!/usr/bin/env python3
"""Page builders for coverage authorization, FDA history, trials and guidance.

Imported by generate_evidence_site.py. Every sentence rendered here is either
verbatim source text (statute, FDA record, registry field, CDC/NIMH page) or a
bare structural label.
"""
import re
from collections import Counter, defaultdict


# --------------------------------------------------------------------------
# coverage authorization — the provider workflow
# --------------------------------------------------------------------------

# Which statute drives which stage of the workflow. Titles are the statute's
# own subject; no interpretation is added.
WORKFLOW = [
    ('Confirm the drug is FDA approved',
     ['HSC-1367.21'],
     'a'),
    ('Establish the condition qualifies',
     ['HSC-1367.21'],
     'a2'),
    ('Document recognition of the use',
     ['HSC-1367.21'],
     'a3'),
    ('Check formulary status',
     ['HSC-1367.24'],
     None),
    ('Submit on the uniform form',
     ['HSC-1367.241'],
     'c'),
    ('Request a step therapy exception where a protocol applies',
     ['HSC-1367.206', 'HSC-1367.244'],
     'b'),
    ('Track the decision clock',
     ['HSC-1367.241'],
     'b'),
    ('Appeal a denial',
     ['HSC-1367.206', 'HSC-1370.4'],
     None),
    ('Escalate to independent review',
     ['HSC-1374.30', 'HSC-1368'],
     None),
]


def subdivisions(statute):
    """Split statute text into top-level subdivisions {letter: [paragraphs]}.

    Nested markers reuse the same "(x)" shape — "(i) The Elsevier Gold
    Standard's Clinical Pharmacology" sits under (B), not subdivision (i) — so
    a paragraph only opens a new subdivision when its letter is the next one
    in sequence.
    """
    out, order = {}, []
    current = None
    expected = ord('a')
    for para in statute['text']:
        m = re.match(r'^\(([a-z])\)', para)
        if m and ord(m.group(1)) == expected:
            current = m.group(1)
            out[current] = []
            order.append(current)
            expected += 1
        if current is None:
            out.setdefault('_', []).append(para)
        else:
            out[current].append(para)
    out['_order'] = order
    return out


def sub(statute, *letters):
    """Paragraphs from the named top-level subdivisions, in source order."""
    parts = subdivisions(statute)
    out = []
    for letter in letters:
        out += parts.get(letter, [])
    return out


def clause(paras, pattern):
    """Paragraphs inside an already-scoped subdivision matching a marker."""
    rx = re.compile(pattern)
    return [p for p in paras if rx.match(p)]


def build_coverage_overview(coverage, mdx_safe, jsx_attr):
    """Step-by-step authorization pathway, each step carrying its statute text."""
    by_key = {f'{s["code"]}-{s["section"]}': s for s in coverage['statutes']}

    lines = [
        '---',
        'title: Coverage authorization',
        'subtitle: California prior authorization pathway for off-label and '
        'nonformulary prescribing',
        'slug: coverage',
        '---',
        '',
        '<Callout intent="info">',
        'California statutory text reproduced from the Legislative Counsel of '
        'California. Not legal advice.',
        '</Callout>',
        '',
    ]

    # ---- the pathway
    lines += ['<Steps toc={true}>', '']

    def step(title, body_lines):
        lines.append(f'<Step title={jsx_attr(title)}>')
        lines.append('')
        lines.extend(body_lines)
        lines.append('</Step>')
        lines.append('')

    s21 = by_key.get('HSC-1367.21')
    s24 = by_key.get('HSC-1367.24')
    s241 = by_key.get('HSC-1367.241')
    s206 = by_key.get('HSC-1367.206')
    s244 = by_key.get('HSC-1367.244')
    s3704 = by_key.get('HSC-1370.4')
    s1374 = by_key.get('HSC-1374.30')
    s1368 = by_key.get('HSC-1368')

    def quote(paras):
        out = []
        for para in paras:
            out += [f'> {mdx_safe(para)}', '>']
        if out:
            out.pop()
        return out + ['']

    def cite(s):
        return [f'[{s["code_name"]} {s["section"]}]({s["url"]}) · '
                f'[Indexed text](/statute-{s["code"].lower()}-'
                f'{s["section"].replace(".", "-")})', '']

    if s21:
        a = sub(s21, 'a')            # off-label coverage conditions
        defs = sub(s21, 'e', 'f')    # statutory definitions

        step('Confirm FDA approval of the drug',
             quote(clause(a, r'^\(1\)')) + cite(s21))

        step('Establish the condition qualifies',
             quote(clause(a, r'^\(2\)|^\(B\) The drug is prescribed')) +
             ['<Accordion title="Statutory definitions">', ''] +
             quote(defs) +
             ['</Accordion>', ''])

        rec = clause(a, r'^\(3\)|^\(A\)|^\(B\) One of|^\(i+\)|^\(C\)')
        step('Document recognition of the use',
             quote(rec) +
             ['<Callout intent="note">',
              'Indexed records that may support the third ground: '
              '[Off-label prescribing](/collection-off-label) · '
              '[Evidence synthesis](/design-meta-analysis) · '
              '[Systematic reviews](/design-systematic-review) · '
              '[Practice guidelines](/design-practice-guideline)',
              '</Callout>', ''])

        step('Assemble the documentation the plan may request',
             quote(sub(s21, 'c', 'd')))

    if s24:
        step('Check formulary status',
             quote(sub(s24, 'a')[:1] + sub(s24, 'b')[:1]) + cite(s24))

    if s241:
        step('Submit on the uniform form',
             quote(sub(s241, 'a')[:1] + sub(s241, 'c')[:1] +
                   clause(sub(s241, 'd'), r'^\((1|2|3)\)') +
                   sub(s241, 'e')[:1]) +
             ['[Form 61-211 and filing routes](/coverage-forms)', ''] +
             cite(s241))

    if s206:
        b = sub(s206, 'b')
        step('Request a step therapy exception where a protocol applies',
             quote(b) +
             (cite(s244) if s244 else []) + cite(s206))

    if s241:
        b241 = sub(s241, 'b')
        clock = [p for p in b241
                 if '72 hours' in p or '24 hours' in p or 'deemed approved' in p]
        exigent = [p for p in sub(s241, 'h') if 'Exigent circumstances' in p]
        step('Track the decision clock',
             quote(clock) +
             (['<Callout intent="warning">',
               mdx_safe(exigent[0]), '</Callout>', ''] if exigent else []))

    if s206:
        step('Appeal a denial', quote(sub(s206, 'c', 'd')) +
             (cite(s3704) if s3704 else []))

    if s1374:
        step('Escalate to independent review',
             quote(sub(s1374, 'a')[:2]) +
             (cite(s1368) if s1368 else []) + cite(s1374))

    lines += ['</Steps>', '']

    # ---- statute index
    lines += ['## Authorities', '',
              '| Citation | Subject | Full text |',
              '| --- | --- | --- |']
    for s in coverage['statutes']:
        lines.append(f'| {s["code_name"]} {s["section"]} '
                     f'| {mdx_safe(s["title"])} '
                     f'| [Legislative Counsel]({s["url"]}) |')
    for r in coverage.get('regulations', []):
        lines.append(f'| {r["cite"]} | {mdx_safe(r["title"])} '
                     f'| [Full text]({r["url"]}) |')
    lines.append('')
    return '\n'.join(lines)


def build_coverage_forms(coverage, mdx_safe, jsx_attr):
    lines = [
        '---',
        'title: Forms and filing',
        'slug: coverage-forms',
        '---',
        '',
    ]
    for f in coverage['forms']:
        lines += [f'## {mdx_safe(f["name"])}', '']
        rows = [('Issuer', f['issuer']), ('Authority', f['authority'])]
        if f.get('revision'):
            rows.append(('Revision', f['revision']))
        lines += ['| Field | Value |', '| --- | --- |']
        lines += [f'| {k} | {mdx_safe(v)} |' for k, v in rows]
        lines += ['', f'> {mdx_safe(f["note"])}', '']
        lines += ['<CardGroup cols={2}>']
        for name, url in f['mirrors']:
            lines.append(f'  <Card title={jsx_attr(name)} '
                         f'icon="fa-regular fa-file-pdf" href="{url}">')
            lines.append('  </Card>')
        lines += ['</CardGroup>', '']
    return '\n'.join(lines)


def build_statute_page(s, mdx_safe):
    lines = [
        '---',
        f'title: "{s["code_name"]} {s["section"]}"',
        f'slug: statute-{s["code"].lower()}-{s["section"].replace(".", "-")}',
        '---',
        '',
        mdx_safe(s['title']),
        '',
        f'[Legislative Counsel of California]({s["url"]})',
        '',
    ]
    if s.get('amended'):
        lines += [mdx_safe(s['amended']), '']
    lines += ['## Text', '']
    for p in s['text']:
        lines += [mdx_safe(p), '']
    return '\n'.join(lines)


# --------------------------------------------------------------------------
# FDA approval history
# --------------------------------------------------------------------------

def _fmt_date(d):
    if not d or len(d) != 8:
        return d or ''
    return f'{d[:4]}-{d[4:6]}-{d[6:]}'


def build_fda_overview(fda, mdx_safe, jsx_attr, slugify):
    lines = [
        '---',
        'title: FDA approval history',
        'slug: fda',
        '---',
        '',
        '<CardGroup cols={2}>',
    ]
    for d in fda['drugs']:
        if not d['applications']:
            continue
        lines.append(f'  <Card title={jsx_attr(d["name"])} '
                     f'icon="fa-regular fa-file-certificate" '
                     f'href="/fda-{slugify(d["key"])}">')
        lines.append('  </Card>')
    lines += ['</CardGroup>', '']
    return '\n'.join(lines)


def build_fda_drug_page(d, mdx_safe, jsx_attr, slugify):
    lines = [
        '---',
        f'title: "{d["name"]}"',
        f'slug: fda-{slugify(d["key"])}',
        '---',
        '',
    ]

    for app in d['applications']:
        lines += [f'## {app["application"]}', '']
        rows = [('Sponsor', app['sponsor'] or '')]
        if app['brands']:
            rows.append(('Brands', ', '.join(app['brands'])))
        if app['first_approval']:
            rows.append(('Original approval', _fmt_date(app['first_approval'])))
        if app['latest_action']:
            rows.append(('Latest action', _fmt_date(app['latest_action'])))
        lines += ['| Field | Value |', '| --- | --- |']
        lines += [f'| {k} | {mdx_safe(v)} |' for k, v in rows]
        lines += ['', f'[Drugs@FDA record]({app["url"]})', '']

        if app['products']:
            lines += ['<Accordion title="Approved products">', '',
                      '| Brand | Form | Route | Strength | Marketing status |',
                      '| --- | --- | --- | --- | --- |']
            for p in app['products']:
                lines.append(
                    f'| {mdx_safe(p["brand"] or "")} | {mdx_safe(p["form"] or "")} '
                    f'| {mdx_safe(p["route"] or "")} '
                    f'| {mdx_safe("; ".join(p["strengths"]))} '
                    f'| {mdx_safe(p["status"] or "")} |')
            lines += ['', '</Accordion>', '']

        notable = [s for s in app['submissions'] if s['notable']]
        if notable:
            lines += ['<Accordion title="Submission history">', '',
                      '| Date | Submission | Category | Documents |',
                      '| --- | --- | --- | --- |']
            for s in notable:
                docs = ' · '.join(f'[{mdx_safe(x["type"] or "Document")}]({x["url"]})'
                                  for x in s['docs'][:4]) or ''
                label = f'{s["type"]} {s["number"]}'.strip()
                lines.append(f'| {_fmt_date(s["date"])} | {mdx_safe(label)} '
                             f'| {mdx_safe(s["category"] or "")} | {docs} |')
            lines += ['', '</Accordion>', '']

    if d.get('generic_sponsors'):
        lines += ['## Generic applications', '',
                  '<Accordion title="Sponsors">', '',
                  ' · '.join(mdx_safe(s) for s in d['generic_sponsors']),
                  '', '</Accordion>', '']
    return '\n'.join(lines)


# --------------------------------------------------------------------------
# clinical trials feed
# --------------------------------------------------------------------------

PHASE_LABEL = {
    'EARLY_PHASE1': 'Early Phase 1', 'PHASE1': 'Phase 1', 'PHASE2': 'Phase 2',
    'PHASE3': 'Phase 3', 'PHASE4': 'Phase 4', 'NA': 'Not applicable',
}
STATUS_LABEL = {
    'RECRUITING': 'Recruiting', 'NOT_YET_RECRUITING': 'Not yet recruiting',
    'ACTIVE_NOT_RECRUITING': 'Active, not recruiting', 'COMPLETED': 'Completed',
    'TERMINATED': 'Terminated', 'WITHDRAWN': 'Withdrawn',
    'SUSPENDED': 'Suspended', 'UNKNOWN': 'Unknown status',
    'ENROLLING_BY_INVITATION': 'Enrolling by invitation',
}


def _trial_row(t, mdx_safe):
    phases = ', '.join(PHASE_LABEL.get(p, p) for p in t['phases']) or ''
    return (f'| [{t["nctid"]}]({t["url"]}) | {mdx_safe(t["title"] or "")} '
            f'| {phases} | {t["enrollment"] or ""} '
            f'| {STATUS_LABEL.get(t["status"], t["status"] or "")} '
            f'| {t["start"] or ""} |')


def build_trials_feed(trials_data, mdx_safe, jsx_attr, slugify):
    """Running feed: newest registrations, newest posted results, recruiting now."""
    trials = trials_data['trials']
    lines = [
        '---',
        'title: Clinical trials',
        'subtitle: ClinicalTrials.gov registrations and posted results',
        'slug: trials',
        '---',
        '',
    ]

    recruiting = [t for t in trials
                  if t['status'] in ('RECRUITING', 'NOT_YET_RECRUITING',
                                     'ENROLLING_BY_INVITATION')]
    results = sorted([t for t in trials if t['results_posted']],
                     key=lambda t: t['results_posted'], reverse=True)
    recent = sorted(trials, key=lambda t: t['start'] or '', reverse=True)

    head = '| Registration | Title | Phase | Enrolment | Status | Start |'
    sep = '| --- | --- | --- | --- | --- | --- |'

    lines += ['<Tabs>', '']

    lines += ['<Tab title="Recruiting">', '', head, sep]
    lines += [_trial_row(t, mdx_safe) for t in
              sorted(recruiting, key=lambda t: t['start'] or '', reverse=True)]
    lines += ['', '</Tab>', '']

    lines += ['<Tab title="Results posted">', '',
              '| Registration | Title | Phase | Enrolment | Results posted |',
              '| --- | --- | --- | --- | --- |']
    for t in results[:120]:
        phases = ', '.join(PHASE_LABEL.get(p, p) for p in t['phases']) or ''
        lines.append(f'| [{t["nctid"]}]({t["url"]}) | {mdx_safe(t["title"] or "")} '
                     f'| {phases} | {t["enrollment"] or ""} | {t["results_posted"]} |')
    lines += ['', '</Tab>', '']

    lines += ['<Tab title="Recently started">', '', head, sep]
    lines += [_trial_row(t, mdx_safe) for t in recent[:120]]
    lines += ['', '</Tab>', '']

    lines += ['</Tabs>', '']
    return '\n'.join(lines)


def build_trials_drug_page(name, key, trials, mdx_safe, slugify):
    lines = [
        '---',
        f'title: "{name}"',
        f'slug: trials-{slugify(key)}',
        '---',
        '',
    ]
    by_phase = defaultdict(list)
    for t in trials:
        ph = t['phases'][-1] if t['phases'] else 'NA'
        by_phase[ph].append(t)

    order = ['PHASE4', 'PHASE3', 'PHASE2', 'PHASE1', 'EARLY_PHASE1', 'NA']
    for ph in order:
        group = by_phase.get(ph)
        if not group:
            continue
        lines += [f'## {PHASE_LABEL.get(ph, ph)}', '',
                  '| Registration | Title | Enrolment | Status | Start | Results |',
                  '| --- | --- | --- | --- | --- | --- |']
        for t in sorted(group, key=lambda x: x['start'] or '', reverse=True):
            res = f'[Posted]({t["url"]}?tab=results)' if t['has_results'] else ''
            lines.append(
                f'| [{t["nctid"]}]({t["url"]}) | {mdx_safe(t["title"] or "")} '
                f'| {t["enrollment"] or ""} '
                f'| {STATUS_LABEL.get(t["status"], t["status"] or "")} '
                f'| {t["start"] or ""} | {res} |')
        lines.append('')
    return '\n'.join(lines)


# --------------------------------------------------------------------------
# public health guidance (CDC / NIMH, US Government public domain)
# --------------------------------------------------------------------------

def build_guidance_overview(ph, mdx_safe, jsx_attr, slugify):
    lines = [
        '---',
        'title: Public health guidance',
        'slug: guidance',
        '---',
        '',
        '<CardGroup cols={2}>',
    ]
    for p in ph['pages']:
        lines.append(f'  <Card title={jsx_attr(p["title"])} '
                     f'icon="fa-regular fa-notes-medical" '
                     f'href="/guidance-{slugify(p["key"])}">')
        lines.append(f'    {mdx_safe(p["agency"])}')
        lines.append('  </Card>')
    lines += ['</CardGroup>', '']
    return '\n'.join(lines)


def build_guidance_page(p, mdx_safe, slugify):
    lines = [
        '---',
        f'title: {_yq(p["title"])}',
        f'slug: guidance-{slugify(p["key"])}',
        '---',
        '',
        f'{mdx_safe(p["agency"])} · [Source]({p["url"]})',
        '',
    ]
    for sec in p['sections']:
        if sec['heading']:
            level = '##' if sec['level'] == 2 else '###'
            lines += [f'{level} {mdx_safe(sec["heading"])}', '']
        for para in sec['paragraphs']:
            lines += [mdx_safe(para), '']
        for b in sec['bullets']:
            lines.append(f'- {mdx_safe(b)}')
        if sec['bullets']:
            lines.append('')
    return '\n'.join(lines)


def _yq(text):
    return '"' + str(text).replace('\\', '\\\\').replace('"', '\\"') + '"'
