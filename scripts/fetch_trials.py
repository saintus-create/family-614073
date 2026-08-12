#!/usr/bin/env python3
"""Harvest ClinicalTrials.gov v2 into fern/data/trials.json.

Captures registered interventional trials for each drug, including posted
results where the sponsor has reported them, plus the countries each trial
recruited in (used for the international coverage axis).
"""
import json
import pathlib
import time
import urllib.parse
import urllib.request

API = 'https://clinicaltrials.gov/api/v2/studies'
OUT = pathlib.Path(__file__).resolve().parent.parent / 'fern' / 'data' / 'trials.json'

DRUGS = [
    ('lisdexamfetamine', 'Lisdexamfetamine'),
    ('amphetamine', 'Amphetamine'),
    ('methylphenidate', 'Methylphenidate'),
    ('dexmethylphenidate', 'Dexmethylphenidate'),
    ('atomoxetine', 'Atomoxetine'),
    ('guanfacine', 'Guanfacine'),
    ('viloxazine', 'Viloxazine'),
]

FIELDS = ','.join([
    'NCTId', 'BriefTitle', 'OfficialTitle', 'OverallStatus', 'Phase',
    'StudyType', 'EnrollmentCount', 'LocationCountry', 'LeadSponsorName',
    'StartDate', 'PrimaryCompletionDate', 'CompletionDate', 'Condition',
    'InterventionName', 'InterventionType', 'PrimaryOutcomeMeasure',
    'HasResults', 'ResultsFirstPostDate', 'StdAge', 'Sex',
    'DesignAllocation', 'DesignInterventionModel', 'DesignMasking',
])


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'evidence-index'})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode())
        except Exception as exc:
            if i == tries - 1:
                print(f'    failed: {exc}')
                return None
            time.sleep(2 * (i + 1))
    return None


def flat(study):
    ps = study.get('protocolSection', {})
    ident = ps.get('identificationModule', {})
    status = ps.get('statusModule', {})
    design = ps.get('designModule', {})
    di = design.get('designInfo', {}) or {}
    arms = ps.get('armsInterventionsModule', {})
    conds = ps.get('conditionsModule', {})
    outcomes = ps.get('outcomesModule', {}) or {}
    locs = ps.get('contactsLocationsModule', {}) or {}
    spons = ps.get('sponsorCollaboratorsModule', {}) or {}
    elig = ps.get('eligibilityModule', {}) or {}

    countries = sorted({l.get('country') for l in (locs.get('locations') or [])
                        if l.get('country')})
    return {
        'nctid': ident.get('nctId'),
        'title': ident.get('briefTitle'),
        'official_title': ident.get('officialTitle'),
        'status': status.get('overallStatus'),
        'start': (status.get('startDateStruct') or {}).get('date'),
        'completion': (status.get('completionDateStruct') or {}).get('date'),
        'results_posted': status.get('resultsFirstPostDateStruct', {}).get('date'),
        'has_results': bool(study.get('hasResults')),
        'phases': design.get('phases') or [],
        'study_type': design.get('studyType'),
        'enrollment': (design.get('enrollmentInfo') or {}).get('count'),
        'allocation': di.get('allocation'),
        'model': di.get('interventionModel'),
        'masking': ((di.get('maskingInfo') or {}).get('masking')),
        'sponsor': (spons.get('leadSponsor') or {}).get('name'),
        'conditions': conds.get('conditions') or [],
        'interventions': [i.get('name') for i in (arms.get('interventions') or [])
                          if i.get('name')],
        'primary_outcomes': [o.get('measure') for o in
                             (outcomes.get('primaryOutcomes') or [])][:4],
        'countries': countries,
        'ages': elig.get('stdAges') or [],
        'url': f'https://clinicaltrials.gov/study/{ident.get("nctId")}',
    }


def fetch(drug):
    out, token = [], None
    while True:
        q = {'query.intr': drug, 'pageSize': '200',
             'filter.overallStatus': ','.join([
                 'COMPLETED', 'RECRUITING', 'ACTIVE_NOT_RECRUITING',
                 'ENROLLING_BY_INVITATION', 'NOT_YET_RECRUITING',
                 'TERMINATED', 'WITHDRAWN', 'SUSPENDED', 'UNKNOWN']),
             'fields': FIELDS}
        if token:
            q['pageToken'] = token
        data = get(f'{API}?{urllib.parse.urlencode(q)}')
        if not data:
            break
        out += [flat(s) for s in data.get('studies', [])]
        token = data.get('nextPageToken')
        if not token:
            break
        time.sleep(0.3)
    return out


def main():
    seen, drugs = {}, []
    for key, label in DRUGS:
        print(f'{label} …')
        trials = [t for t in fetch(key) if t['nctid']]
        # interventional only; observational registrations add noise here
        trials = [t for t in trials if t['study_type'] == 'INTERVENTIONAL']
        trials.sort(key=lambda t: t['start'] or '', reverse=True)
        drugs.append({'key': key, 'name': label,
                      'nctids': [t['nctid'] for t in trials]})
        for t in trials:
            seen.setdefault(t['nctid'], t).setdefault('drugs', [])
            if key not in seen[t['nctid']]['drugs']:
                seen[t['nctid']]['drugs'].append(key)
        print(f'  {len(trials)} interventional trials')
        time.sleep(0.3)

    trials = sorted(seen.values(), key=lambda t: t['start'] or '', reverse=True)
    OUT.write_text(json.dumps({'drugs': drugs, 'trials': trials}, indent=1))
    with_results = sum(1 for t in trials if t['has_results'])
    countries = {c for t in trials for c in t['countries']}
    print(f'\nWrote {OUT} — {len(trials)} unique trials, '
          f'{with_results} with posted results, {len(countries)} countries')


if __name__ == '__main__':
    main()
