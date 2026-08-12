#!/usr/bin/env python3
"""Harvest California coverage-authorization law into fern/data/coverage.json.

Pulls the operative statute text verbatim from the Legislative Counsel's
official California Legislative Information site, plus the DMHC/CDI uniform
prior authorization form and the independent review pathway. California
statutes are not subject to copyright (Gov. Code 6252-6253 public records;
Cal. Code Regs. text likewise published by the state).
"""
import html
import json
import pathlib
import re
import subprocess
import time

OUT = (pathlib.Path(__file__).resolve().parent.parent
       / 'fern' / 'data' / 'coverage.json')

BASE = ('https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml'
        '?lawCode={code}&sectionNum={num}')

# (code, section, short title, why it matters in the workflow)
SECTIONS = [
    ('HSC', '1367.21', 'Off-label coverage — health care service plans',
     'Sets the three independent grounds on which a plan may not exclude an '
     'FDA-approved drug prescribed for an unapproved use.'),
    ('INS', '10123.195', 'Off-label coverage — health insurers',
     'The parallel obligation for policies regulated by the Department of '
     'Insurance rather than the DMHC.'),
    ('HSC', '1367.24', 'Nonformulary drug authorization',
     'The route when the drug is not on the plan formulary.'),
    ('HSC', '1367.241', 'Prior authorization form and decision deadlines',
     'Mandates the uniform form and the 72-hour / 24-hour decision clock, '
     'including the deemed-approved remedy.'),
    ('HSC', '1367.206', 'Step therapy exceptions',
     'The five statutory grounds for overriding a step therapy protocol.'),
    ('HSC', '1367.244', 'Step therapy exception requests',
     'Confirms a step therapy exception is submitted and answered like a prior '
     'authorization.'),
    ('HSC', '1370.4', 'Experimental or investigational therapy review',
     'External review when a denial rests on the treatment being experimental.'),
    ('HSC', '1374.30', 'Independent Medical Review System',
     'The enrollee-initiated independent medical review, binding on the plan.'),
    ('HSC', '1368', 'Plan grievance process',
     'The enrollee grievance that must generally precede independent review.'),
]

# Documents a provider actually files or cites.
FORMS = [
    {
        'name': 'Prescription Drug Prior Authorization or Step Therapy '
                'Exception Request Form (No. 61-211)',
        'issuer': 'CA Department of Managed Health Care / Department of Insurance',
        'revision': 'Revised 12/2016',
        'authority': '28 CCR 1300.67.241(a); Health & Safety Code 1367.241(c)-(d)',
        'note': 'Plans must use and accept only this form. It may not exceed two '
                'pages, and plans must make it electronically available.',
        'mirrors': [
            ('Blue Shield of California Promise Health Plan',
             'https://www.blueshieldca.com/content/dam/bsca/en/shared/documents/'
             'legacy/BSP_2019_Prescription%20Drug%20Prior%20Authorization%20Step'
             '%20Therapy%20Exception%20Request%20Form.pdf'),
            ('UnitedHealthcare (California commercial)',
             'https://www.uhcprovider.com/content/dam/provider/docs/public/'
             'prior-auth/drugs-pharmacy/CA-Pharmacy-Prior-Auth-Form.pdf'),
            ('Health Net of California',
             'https://uc.healthnetcalifornia.com/content/dam/centene/healthnet/'
             'pdfs/groups/ca_universal_pa_form.pdf'),
            ('Anthem Blue Cross (Medi-Cal)',
             'https://providers.anthem.com/docs/gpp/california-provider/'
             'CA_CAID_PrescriptionDrugPriorAuthForm.pdf'),
        ],
    },
    {
        'name': 'Independent Medical Review / Complaint Form',
        'issuer': 'CA Department of Managed Health Care Help Center',
        'revision': None,
        'authority': 'Health & Safety Code 1374.30',
        'note': 'Filed by the enrollee after the plan issues its final denial, '
                'or after 30 days without a decision.',
        'mirrors': [
            ('DMHC Help Center — file a complaint',
             'https://www.dmhc.ca.gov/FileaComplaint.aspx'),
            ('DMHC Independent Medical Review',
             'https://www.dmhc.ca.gov/FileaComplaint/'
             'IndependentMedicalReviewComplaintForms.aspx'),
        ],
    },
    {
        'name': 'Medi-Cal Rx Prior Authorization Request Form',
        'issuer': 'CA Department of Health Care Services / Medi-Cal Rx',
        'revision': None,
        'authority': 'Welf. & Inst. Code 14185; Medi-Cal Rx Provider Manual',
        'note': 'Medi-Cal managed care is carved out of the Health & Safety Code '
                '1367.241 deadlines; pharmacy benefits run through Medi-Cal Rx.',
        'mirrors': [
            ('Medi-Cal Rx provider portal',
             'https://medi-calrx.dhcs.ca.gov/provider/forms/'),
        ],
    },
]

# 28 CCR 1300.67.241 is regulation, not statute; Cornell mirrors it reliably.
REGULATIONS = [
    ('28 CCR 1300.67.241',
     'Prescription Drug Prior Authorization or Step Therapy Exception Request '
     'Form Process',
     'https://www.law.cornell.edu/regulations/california/28-CCR-1300.67.241'),
]


def curl(url, tries=3):
    for i in range(tries):
        r = subprocess.run(['curl', '-sL', '--compressed', '--max-time', '60', url],
                           capture_output=True, text=True)
        if r.returncode == 0 and len(r.stdout) > 1500:
            return r.stdout
        time.sleep(2 * (i + 1))
    return None


def clean(s):
    s = re.sub(r'(?s)<[^>]+>', '', s)
    s = html.unescape(s)
    s = s.replace('\u2019', '\u2019').replace('\xa0', ' ')
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()


def parse_statute(raw):
    """Return (paragraphs[], amended_note) from a leginfo code page."""
    m = re.search(r'(?s)<div id="manylawsections">(.*?)</div>\s*</div>', raw)
    body = m.group(1) if m else raw

    # each statutory paragraph sits in its own <p>
    paras = []
    for p in re.findall(r'(?s)<p[^>]*>(.*?)</p>', body):
        txt = clean(p)
        txt = re.sub(r'\s*\n\s*', ' ', txt)
        if txt and len(txt) > 3:
            paras.append(txt)

    amended = None
    for i, p in enumerate(paras):
        if re.match(r'^\(?(Amended|Added|Repealed|Renumbered)', p):
            amended = p.strip('()')
            paras = paras[:i]
            break

    # drop the code/division/chapter/article headers leginfo repeats
    drop = re.compile(r'^(Health and Safety Code|Insurance Code|DIVISION |CHAPTER |'
                      r'ARTICLE |PART |\( ?(Division|Chapter|Article|Part|Heading))',
                      re.I)
    paras = [p for p in paras if not drop.match(p)]
    # the leading bare section number
    paras = [p for p in paras if not re.fullmatch(r'\d+\.\d+\.?', p)]
    return paras, amended


def main():
    statutes = []
    for code, num, title, why in SECTIONS:
        url = BASE.format(code=code, num=num)
        print(f'{code} {num} …')
        raw = curl(url)
        if not raw:
            print('    failed')
            continue
        paras, amended = parse_statute(raw)
        if not paras:
            print('    no text parsed')
            continue
        statutes.append({
            'code': code,
            'code_name': ('Health & Safety Code' if code == 'HSC'
                          else 'Insurance Code'),
            'section': num,
            'title': title,
            'relevance': why,
            'text': paras,
            'amended': amended,
            'url': url,
        })
        print(f'    {len(paras)} paragraphs')
        time.sleep(0.4)

    regs = []
    for cite, title, url in REGULATIONS:
        print(f'{cite} …')
        regs.append({'cite': cite, 'title': title, 'url': url})

    OUT.write_text(json.dumps(
        {'statutes': statutes, 'regulations': regs, 'forms': FORMS}, indent=1))
    print(f'\nWrote {OUT} — {len(statutes)} statutes, {len(regs)} regulations, '
          f'{len(FORMS)} form sets')


if __name__ == '__main__':
    main()
