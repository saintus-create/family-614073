# COHS Clinical Evidence & Off-Label Workflow Bank

A source-linked research and workflow bank for understanding off-label medication requests, clinical evidence, FDA labeling, California authority, coverage routing, authorization, decisions, and appeals in County Organized Health System (COHS) settings.

The repository's evidence catalogue remains the source of truth for PubMed literature, FDA/DailyMed labeling, Drugs@FDA approval history, ClinicalTrials.gov registrations, California coverage authorities, public-health guidance, and CenCal/Medi-Cal Rx authorization facts. The COHS workflow layer adds role-aware documentation and routing without turning those sources into unsupported clinical or legal conclusions.

## Product boundary

The workflow bank does **not** prescribe, choose treatment for an individual, guarantee coverage, replace an authorization decision, or provide legal advice.

“Everything” is scoped by jurisdiction, plan/program, benefit channel, medication/formulation, and effective date. Where the repository does not establish a current answer, the interface says **verification required** rather than implying universal coverage or a universal legal rule.

## Source pipeline

```text
scripts/fetch_pubmed.py        -> fern/data/studies.json
scripts/fetch_labels.py        -> fern/data/labels.json
scripts/fetch_fda.py           -> fern/data/fda.json
scripts/fetch_trials.py        -> fern/data/trials.json
scripts/fetch_coverage.py      -> fern/data/coverage.json
scripts/fetch_public_health.py -> fern/data/public_health.json
manual/source-linked data      -> fern/data/cencal_prior_authorization.json
                                   + fern/data/legal/off-label/**
generate_evidence_site.py      -> fern/docs/pages/**
```

Those data files are the source of truth for generated evidence pages. Edit the data or generator rather than hand-editing generated catalogue output.

## COHS workflow bank

The primary entry point is `/cohs-workflow`. It contains:

- role-based workflows for members, providers, pharmacists, reviewers/staff, and legal/compliance reviewers
- a request-packet checklist
- approved-label versus off-label framing
- pharmacy-benefit versus medical-benefit routing
- decision-state interpretation for approvals, partial approvals, modifications, deferrals, denials, and information requests
- a denial and appeals navigator
- a scoped completeness dashboard
- provenance and verification boundaries

The initial authorization evidence is strongest for the CenCal Health / Medi-Cal Rx pathway represented by `fern/data/cencal_prior_authorization.json`. Pharmacy-benefit PA is distinguished from CenCal medical-benefit PAD/TAR processing. Current formularies, forms, contracts, notices, submission routes, and effective dates still require verification before operational use.

## Existing California off-label authority layer

`fern/docs/pages/california-off-label/` contains the structured prescribing-authority, evidence, consent, documentation, additional-requirements, claims/decisions, and provenance workspace. It is deliberately kept separate from payer coverage: a clinician's authority to prescribe and a payer's obligation to authorize or cover are different questions.

## Evidence catalogue

The research catalogue includes PubMed studies, ClinicalTrials.gov registrations, FDA/DailyMed labels, Drugs@FDA approval records, California coverage authorities, public-health guidance, and CenCal/Medi-Cal Rx source-linked workflow facts.

Study regimens describe study conditions, not recommendations. Regulatory guidance describes approved US prescribing information. The literature catalogue is not a systematic review, and absence from the index does not establish absence of evidence.

## Verification

```bash
python3 scripts/fetch_pubmed.py --verify
python3 generate_evidence_site.py
fern check
```

The project also has GitHub Actions checks and documentation publishing workflows. Fern CLI validation may remain environment/CI dependent when Fern is not installed locally.

## Scope and provenance

Every material workflow proposition should be understood through its jurisdiction, plan/program, benefit channel, source authority, effective/publication date, and verification state. The legal/off-label manifest defines four provenance states: `verified`, `source-derived`, `review-required`, and `unreviewed`.

See `docs-off-label-workflow-requirements.md` for the implementation contract and completeness rules.
