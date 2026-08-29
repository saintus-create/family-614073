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
# CenCal Health prior authorization / TAR workflow
# --------------------------------------------------------------------------

def build_cencal_prior_authorization(data, mdx_safe, jsx_attr):
    """Render the CenCal operational analysis as MDX content."""

    wic_14087_54 = 'https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=WIC&sectionNum=14087.54'
    wic_14087_5 = 'https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=WIC&sectionNum=14087.5'
    history = 'https://www.cencalhealth.org/explore-cencal-health/our-history/'
    medical_pharmacy = 'https://www.cencalhealth.org/providers/pharmacy/medical-pharmacy-management/'
    pharmacy_benefit = 'https://www.cencalhealth.org/health-plans/medi-cal/pharmacy-benefits/'
    medi_cal_rx_forms = 'https://medi-calrx.dhcs.ca.gov/provider/forms/'
    treatment_authorization = 'https://www.cencalhealth.org/providers/authorizations/treatment-authorization/'
    apl_21_011 = 'https://www.dhcs.ca.gov/file/apl21-011-pdf/'
    boilerplate = 'https://www.dhcs.ca.gov/providers-partners/medi-cal-managed-care-boilerplate-contracts/'
    audit = 'https://www.dhcs.ca.gov/services/Documents/CenCal-main-and-SSS-Reports.pdf'
    ecm = 'https://www.cencalhealth.org/providers/enhanced-care-management/'
    wcm = 'https://www.cencalhealth.org/providers/ccs-whole-child-model/'
    careconnect = 'https://www.cencalhealth.org/providers/eligibility/'
    transportation = 'https://www.cencalhealth.org/members/transportation/'
    grievances = 'https://www.cencalhealth.org/health-plans/medi-cal/grievances-and-appeals/'
    dmhc_faq = 'https://www.dmhc.ca.gov/FileaComplaint/FrequentlyAskedQuestions.aspx'

    return f'''---
title: Operational and Regulatory Analysis of CenCal Health as a County Organized Health System
subtitle: COHS authority, medical-benefit administration, Medi-Cal Rx carve-outs, utilization management, care coordination and appeal pathways.
slug: cencal-health/prior-authorization
---

## Statutory Origin and Enabling Legal Framework

CenCal Health operates through the county health-system authority established in California Welfare and Institutions Code section 14087.54. The statute permits one or more county boards of supervisors to establish a special commission to arrange publicly assisted medical care, improve quality, and promote cost efficiency. CenCal’s institutional predecessor, the Santa Barbara Health Initiative, began operations in 1983; CenCal Health later expanded into San Luis Obispo County in 2008. CenCal identifies the resulting plan as a publicly funded health program for residents of Santa Barbara and San Luis Obispo counties. [WIC § 14087.54]({wic_14087_54}) [CenCal history]({history})

Section 14087.54 authorizes the commission to negotiate the exclusive contract described in section 14087.5 and to arrange services under the Medi-Cal statutory framework. When the enabling ordinance is enacted, the commission receives the rights, powers, duties, privileges, and immunities assigned to the county under the county health-system article. The statute also provides that the commission is a public entity separate from the participating counties, and that its statutory, contractual, and other obligations are obligations of the commission alone, not of the county or the state. [WIC § 14087.54]({wic_14087_54}) [WIC § 14087.5]({wic_14087_5})

The same statutory framework preserves a competitive provider environment. County-owned facilities do not occupy a superior or inferior contracting position solely because the commission was created by county ordinance. Section 14087.54 also prohibits the use of Medi-Cal payments or reserves for non-Medi-Cal programs that the commission may administer. [WIC § 14087.54]({wic_14087_54})

## Governance Architecture and Regional Operating Scope

CenCal Health is governed by a thirteen-member Board of Directors appointed by the Santa Barbara and San Luis Obispo County Boards of Supervisors. CenCal describes the board as including local government representatives, physicians, hospital representatives, member representatives, other health-care provider representatives, and business representatives. [CenCal history]({history})

Within the County Organized Health System model, CenCal functions as the single Medi-Cal managed-care plan for its two-county service area. DHCS audit materials identify the legal entity as Santa Barbara San Luis Obispo Regional Health Authority, doing business as CenCal Health, and reported 241,571 Medi-Cal members as of December 2024. [DHCS FY 2024-25 audit]({audit})

| Organizational metric | Operational specification | Primary authority |
| --- | --- | --- |
| Legal entity | Santa Barbara San Luis Obispo Regional Health Authority, dba CenCal Health | [DHCS audit]({audit}) |
| Operating model | Single-plan County Organized Health System | [WIC § 14087.5]({wic_14087_5}) |
| Service area | Santa Barbara County and San Luis Obispo County | [CenCal history]({history}) |
| Governing body | Thirteen-member appointed Board of Directors | [CenCal history]({history}) |
| Reported Medi-Cal enrollment | 241,571 members as of December 2024 | [DHCS audit]({audit}) |
| Contract framework | DHCS managed-care contract, plan-specific exhibits, statutes, regulations and All Plan Letters | [DHCS boilerplate contracts]({boilerplate}) |

## Medical Benefit Administration and Pharmacy Carve-Outs

CenCal’s benefit administration turns on the distinction between pharmacy claims and medical claims. Since January 1, 2022, Medi-Cal Rx has administered the outpatient pharmacy benefit for CenCal Medi-Cal members. CenCal therefore does not adjudicate ordinary pharmacy point-of-sale claims or pharmacy prior authorizations for outpatient retail prescriptions covered through Medi-Cal Rx. [CenCal pharmacy benefits]({pharmacy_benefit}) [Medi-Cal Rx forms]({medi_cal_rx_forms})

CenCal retains responsibility for physician-administered drugs when the medication is supplied and administered by a clinician in a medical setting and billed on a medical or institutional claim. CenCal’s Medical Pharmacy Management materials state that physician-administered drug authorization requests are evaluated through the plan’s medical pharmacy process, using the applicable PAD list, authorization criteria, and medical-necessity documentation. [Medical Pharmacy Management]({medical_pharmacy})

CenCal also identifies five medication classes that are carved out of its benefit and reviewed or billed through State of California Fee-for-Service Medi-Cal for authorization consideration and reimbursement for both pharmacy and medical claims: antivirals; alcohol and heroin detoxification and dependency treatment drugs; blood-factor products for clotting-factor disorders; erectile-dysfunction drugs; and psychiatric drugs. [Medical Pharmacy Management]({medical_pharmacy})

| Therapeutic benefit | Administrative entity | Authorization pathway |
| --- | --- | --- |
| Outpatient retail pharmacy | DHCS through Medi-Cal Rx | Medi-Cal Rx formulary, portal and DHCS 6560 process |
| Physician-administered drugs | CenCal Health Pharmacy Services | CenCal Provider Portal or medical Treatment Authorization Request |
| Antivirals | State Fee-for-Service Medi-Cal | State FFS review and reimbursement |
| Alcohol and heroin detoxification and dependency treatment drugs | State Fee-for-Service Medi-Cal | State FFS review and reimbursement |
| Blood-factor products for clotting-factor disorders | State Fee-for-Service Medi-Cal | State FFS review and reimbursement |
| Erectile-dysfunction drugs | State Fee-for-Service Medi-Cal | State FFS review and reimbursement |
| Psychiatric drugs | State Fee-for-Service Medi-Cal | State FFS review and reimbursement |

## Utilization Management and Prior Authorization Procedures

CenCal’s utilization-management process evaluates whether requested medical services and physician-administered drugs satisfy applicable benefit rules and medical-necessity criteria. Before rendering a service that may require authorization, providers should verify the governing rule through CenCal’s authorization resources, the HCPCS or CPT authorization search process, and the current physician-administered drug list when the request involves a medical-pharmacy product. [Treatment Authorization]({treatment_authorization}) [Medical Pharmacy Management]({medical_pharmacy})

For retail pharmacy requests, the prescriber proceeds through Medi-Cal Rx by submitting the DHCS 6560 prior authorization form or by using an approved electronic submission route. For physician-administered drugs, the provider submits a CenCal medical authorization request before administration when the PAD list or code-search result requires a TAR. [Medi-Cal Rx forms]({medi_cal_rx_forms}) [Medical Pharmacy Management]({medical_pharmacy})

Clinical submissions should identify the member, diagnosis, requested drug or procedure code, strength, route, dose, units or quantity, frequency, duration, prior treatment history, contraindications or failed alternatives, and the clinical rationale supporting the requested regimen. Off-label, non-preferred, quantity-limit, and multiple-dose requests require a record that connects the requested service to objective medical necessity criteria and the available clinical evidence. [Treatment Authorization]({treatment_authorization}) [Medical Pharmacy Management]({medical_pharmacy})

| Authorization category | Primary use | Submission route |
| --- | --- | --- |
| Medical 50-1 TAR | Outpatient procedures, specialty services, medical treatments, durable medical equipment and physician-administered drugs | CenCal Provider Portal or designated authorization form |
| Facility 18-1 authorization | Acute inpatient and facility-level requests | CenCal Provider Portal |
| Long-Term Care 20-1 authorization | Skilled nursing, subacute and long-term care authorization | CenCal Provider Portal |
| Referral Authorization Form | Primary-care referral to network specialty care | CenCal referral process |
| Medi-Cal Rx prior authorization | Outpatient retail pharmacy benefit | Medi-Cal Rx portal, DHCS 6560 or electronic PA route |

## Review Timelines and Adjudication Standards

CenCal’s provider materials state that routine TARs are processed within five working days when appropriate documentation is supplied, may take up to fourteen days when additional documentation is required, and that expedited TARs are processed within three working days. Retroactive review may take up to thirty calendar days. DHCS All Plan Letter 21-011 sets the managed-care authorization standards for non-pharmacy prospective and concurrent requests, including five-business-day and fourteen-calendar-day limits for standard matters and a seventy-two-hour standard for expedited matters when the regulatory criteria are met. [Treatment Authorization]({treatment_authorization}) [DHCS APL 21-011]({apl_21_011})

| Review category | Timeline reflected in the cited materials | Source |
| --- | --- | --- |
| Emergency services | Prior authorization is not required for emergency services | [DHCS APL 21-011]({apl_21_011}) |
| Expedited authorization | CenCal states three working days; DHCS standards require decision and notice within the applicable expedited limit | [Treatment Authorization]({treatment_authorization}) [DHCS APL 21-011]({apl_21_011}) |
| Standard authorization | CenCal states five working days with appropriate documentation and up to fourteen days when additional information is needed | [Treatment Authorization]({treatment_authorization}) |
| Retroactive review | CenCal states up to thirty calendar days | [Treatment Authorization]({treatment_authorization}) |

If the submission lacks the information necessary for review, the plan may defer the request and ask for specified clinical documentation. If a request is denied, deferred, or modified, CenCal states that the returned TAR identifies the reason and includes the appeal process. [Treatment Authorization]({treatment_authorization})

## Provider TAR Appeal Framework

A provider who receives a denial, deferral, or modification of a CenCal TAR may contact the physician reviewer or submit a TAR appeal. CenCal instructs providers to file the TAR Appeal Form within ninety calendar days of the original decision and to include the original TAR and denial notice, a written explanation of why the denial or modification should be overturned, and documentation supporting reversal. [Treatment Authorization]({treatment_authorization})

## Integrated Care Coordination and CalAIM Programs

CenCal administers Enhanced Care Management under CalAIM for eligible members with complex medical, behavioral, and social needs. CenCal describes ECM as intensive care management that coordinates physical health, behavioral health, long-term services, oral health, and social determinants of health through assigned care-management resources and contracted community providers. [Enhanced Care Management]({ecm})

CenCal also administers the California Children’s Services Whole Child Model for eligible members in Santa Barbara and San Luis Obispo counties. Under that model, CenCal is responsible for payment, authorizations, care coordination, and claims processing for CCS-eligible CenCal members, while county CCS programs continue to determine CCS eligibility. [CCS Whole Child Model]({wcm})

For dual-eligible members, CenCal CareConnect is CenCal’s Dual Eligible Special Needs Plan for individuals who qualify for both Medicare and Medi-Cal and reside in Santa Barbara or San Luis Obispo County. CenCal describes the product as combining Medicare, Medicare prescription drug coverage, and Medi-Cal benefits into a single coordinated plan. [CenCal eligibility]({careconnect})

## Medical Transportation Administration

CenCal administers non-emergency medical transportation and non-medical transportation benefits for members who need transportation to covered services. NEMT is used when the member requires specialized transport or assistance because of medical limitations; NMT covers less intensive transportation arrangements for members who can use ordinary transportation with coordination support. [Transportation]({transportation})

## Member Grievances, Appeals and External Review

CenCal’s member grievance and appeal system permits members to file complaints and appeals without retaliation. CenCal states that a member may appeal a denial, delay, modification, or other adverse plan decision verbally, in writing, online, or through Member Services within sixty days from the date of the decision. A provider filing an appeal on the member’s behalf must obtain written member consent. [Grievances and Appeals]({grievances})

Standard member appeals are resolved within thirty calendar days. Expedited appeals are available when the ordinary timeframe could seriously jeopardize the member’s life, physical or mental health, or ability to attain, maintain, or regain maximum function. DHCS APL 21-011 also describes the State Fair Hearing framework after exhaustion of the managed-care appeal process. [Grievances and Appeals]({grievances}) [DHCS APL 21-011]({apl_21_011})

| Dispute stage | Initiation window | Decision framework | Governing body |
| --- | --- | --- | --- |
| Member appeal | Sixty days from the adverse decision notice | Thirty calendar days standard; expedited review when criteria are met | CenCal Grievance and Appeals |
| Provider TAR appeal | Ninety calendar days from the original TAR decision | Provider appeal with clinical justification and supporting records | CenCal Medical Management |
| State Fair Hearing | After managed-care appeal exhaustion, subject to DHCS/CDSS deadlines | Administrative hearing process | California Department of Social Services |
| Independent Medical Review | Depends on DMHC jurisdiction and eligibility criteria | DMHC review when available | Department of Managed Health Care |

## Strategic Synthesis

CenCal Health’s operating structure reflects the County Organized Health System model: a locally governed public entity with a DHCS managed-care contract, a defined two-county service area, and responsibility for administering covered managed-care benefits through regional provider networks. The model centralizes medical-benefit administration while preserving state-level carve-outs for Medi-Cal Rx pharmacy claims and specified Fee-for-Service drug categories.

For medication-related requests, the controlling operational question is the benefit channel. Retail pharmacy claims proceed through Medi-Cal Rx. Physician-administered drugs billed on medical claims remain within CenCal’s medical-pharmacy authorization process unless a state carve-out applies. Effective submissions therefore identify the channel first, then align the clinical record, billing code, dose, quantity, duration, prior therapies, evidence base, and appeal route to that channel.

## Principal Source Materials

- [California Legislative Information — Welfare and Institutions Code section 14087.54]({wic_14087_54})
- [California Legislative Information — Welfare and Institutions Code section 14087.5]({wic_14087_5})
- [DHCS — Managed Care Boilerplate Contracts]({boilerplate})
- [DHCS — All Plan Letter 21-011]({apl_21_011})
- [DHCS — FY 2024-25 Medical Audit of Santa Barbara San Luis Obispo Regional Health Authority dba CenCal Health]({audit})
- [CenCal Health — Our History]({history})
- [CenCal Health — Medical Pharmacy Management]({medical_pharmacy})
- [CenCal Health — Treatment Authorization]({treatment_authorization})
- [CenCal Health — Grievances and Appeals]({grievances})
- [CenCal Health — Enhanced Care Management]({ecm})
- [CenCal Health — CCS Whole Child Model]({wcm})
- [CenCal Health — Transportation]({transportation})
- [Medi-Cal Rx — Provider Forms]({medi_cal_rx_forms})
- [DMHC — Complaint and IMR Eligibility FAQ]({dmhc_faq})
'''


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
