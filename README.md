# Clinical Evidence Index

A bibliographic clearing house for published research on ADHD and binge-eating
pharmacotherapy — lisdexamfetamine, amphetamines, methylphenidate, atomoxetine and
other non-stimulants.

Every record in the catalogue is fetched from the NCBI PubMed E-utilities API. Titles,
authors, journals, years, abstracts, MeSH headings, DOIs and PMCIDs are reproduced as
PubMed returns them. No metadata is hand-entered.

## How it works

```
scripts/fetch_pubmed.py    ->  fern/data/studies.json   (literature, from PubMed)
scripts/fetch_labels.py    ->  fern/data/labels.json    (approved labelling, from DailyMed)
generate_evidence_site.py  ->  fern/docs/pages/**       (render MDX + nav)
```

Those two JSON files are the single source of truth. Both the pages under
`fern/docs/pages/` and the `navigation` block of `fern/docs.yml` are generated — edit the
data or the generator, never the output.

### Refresh the catalogue

```bash
python3 scripts/fetch_pubmed.py      # re-query PubMed, rewrite studies.json
python3 scripts/fetch_labels.py      # re-pull FDA labels, rewrite labels.json
python3 generate_evidence_site.py    # rebuild all pages and navigation
fern check                           # validate
fern docs dev                        # preview locally
```

### Verify existing records

```bash
python3 scripts/fetch_pubmed.py --verify
```

Re-queries every PMID in the dataset and reports any that no longer resolve or whose
title has drifted from the stored copy. Run this before publishing.

## Catalogue structure

| Axis | Source |
|---|---|
| Collections | one PubMed query each, printed on the collection page |
| Study design | PubMed publication types, with an abstract-text fallback |
| Topics | matched against abstract text; a record can carry several |
| Populations | matched against abstract text |
| Countries / regions | author affiliations on the PubMed record |
| Dosing regimens | abstract wording (once daily, divided doses, XR/IR, titration) |
| Regulatory guidance | DailyMed Structured Product Labels |

Adding a collection means adding one entry to `COLLECTIONS` in `scripts/fetch_pubmed.py`
and re-running both scripts.

### Two kinds of dosing information

These are deliberately kept apart, and the AI prompt is instructed not to conflate them:

- **Study regimens** (`regimen-*` pages) describe what a trial administered. They are
  study conditions, not recommendations.
- **Regulatory guidance** (`regulatory`, `label-*` pages) is approved US prescribing
  information reproduced from DailyMed.

Approved dosing, age limits and controlled-substance scheduling differ by country. The
labels indexed here are US-only; the literature spans 45 countries.

## Conventions

- **Native components only.** Pages are built from Fern's built-in `Badge`, `Callout`,
  `Card`, `CardGroup`, `Accordion`, `Tabs` and `Steps`. No custom CSS or bespoke markup.
- **Theme is hand-maintained.** Colors, logo, typography and `custom.js` in `docs.yml`
  are not touched by the generator; it only rewrites `title`, `navigation` and
  `ai-search`. Keep it that way — commit `d0a9697` records what happened last time the
  generator clobbered those blocks.
- **Abstract text is escaped.** PubMed abstracts contain `<18 years` and `p<0.05`, which
  MDX would otherwise parse as JSX. `mdx_safe()` handles this; route any new
  PubMed-derived text through it.

## Scope

This is a bibliographic index for research use. It reproduces published abstracts and
does not interpret them, rank treatments, or offer medical advice. Collections are
relevance-ranked PubMed samples capped at a fixed size — they are not systematic reviews,
and absence from the index says nothing about a study's quality.
