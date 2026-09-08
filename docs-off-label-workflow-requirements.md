# COHS Off-Label Workflow Bank — Implementation Requirements

## Product boundary

This project is a source-linked decision-support and documentation bank for off-label medication authorization questions in County Organized Health System (COHS) environments. It organizes evidence, regulatory status, benefit-channel routing, authorization workflow, forms, decisions, and appeal paths. It does not prescribe, select treatment for an individual, guarantee coverage, replace an authorization decision, or provide legal advice.

## Scope model

Every workflow record must identify:

- jurisdiction and county
- plan or program
- benefit channel (pharmacy vs medical/physician-administered)
- medication, formulation, and requested use when known
- effective/source date
- source authority and verification state
- known gaps or items requiring current-plan verification

The bank must not imply universal coverage or a universal off-label rule from a single plan source.

## Required workflow layers

1. **Clinical/evidence layer** — approved-label status, off-label classification, study evidence, limitations, contradictory evidence, and provenance.
2. **Regulatory layer** — statutes, regulations, agency guidance, plan contracts/policies, effective dates, and authority type.
3. **Benefit routing layer** — pharmacy benefit versus medical benefit, responsible reviewer, formulary/PAD status, and authorization route.
4. **Submission layer** — required form, electronic/portal/fax route, attachments, urgency, and submission timing.
5. **Decision layer** — approved, partially approved, modified, deferred/pend, denied, and information-request states.
6. **Appeal layer** — reconsideration, internal appeal, peer review where applicable, State Fair Hearing, external/independent review where applicable, and urgent pathways.
7. **Role layer** — member, prescriber/provider, pharmacist, plan reviewer/staff, and legal/compliance reviewer views.
8. **Completeness layer** — what is verified, what is source-derived, what needs current verification, and what is not yet covered.

## Current implementation target

The initial COHS workflow bank is grounded in the repository's existing CenCal Health / Medi-Cal Rx source-linked record. It must clearly distinguish CenCal medical-benefit TAR workflow from the DHCS/Medi-Cal Rx pharmacy-benefit PA workflow.

## UI standard

Use progressive disclosure, descriptive action labels, role tabs, callouts for safety boundaries, and step-based workflows. Do not use dense tables as the primary information architecture, hide critical requirements in tooltips, or use color/icon alone to communicate status. The California map remains contextual decoration rather than the clinical or authorization browser.

## Completeness rule

A workflow is not considered complete merely because a form or policy is linked. Each material fact should carry source, scope, date/verification state, and an explicit gap where the repository does not establish the current answer.
