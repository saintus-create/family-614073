#!/usr/bin/env node
/**
 * Generate doc-format pages (title/description frontmatter + sections,
 * tables, callouts) for each medication, from the repo's data files.
 *
 *   node scripts/generate-docs.mjs
 *
 * Reads  ../fern/data/{labels,fda,trials,studies}.json
 * Writes content/docs/<drug-key>.md
 */
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const here = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.join(here, "..", "..", "fern", "data");
const OUT = path.join(here, "..", "content", "docs");

const load = (f) => JSON.parse(readFileSync(path.join(DATA, f), "utf8"));
const labels = load("labels.json").labels;
const fda = load("fda.json").drugs;
const trials = load("trials.json");
const studies = load("studies.json");

// Internal links point at the uniform MDX pages.
const TRIALS_HREF = "/trials";
const BROWSE_HREF = "/browse";

const PHASE_LABEL = {
  EARLY_PHASE1: "Early Phase 1",
  PHASE1: "Phase 1",
  PHASE2: "Phase 2",
  PHASE3: "Phase 3",
  PHASE4: "Phase 4",
  NA: "Not applicable",
};

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function fmtDate(yyyymmdd) {
  if (!yyyymmdd || String(yyyymmdd).length !== 8) return "";
  const s = String(yyyymmdd);
  return `${MONTHS[+s.slice(4, 6) - 1]} ${+s.slice(6, 8)}, ${s.slice(0, 4)}`;
}

// Which PubMed collection covers a drug key (studies.json uses 4 keys).
const COLLECTION_FOR = {
  lisdexamfetamine: "lisdexamfetamine",
  amphetamine: "amphetamine",
  methylphenidate: "methylphenidate",
  dexmethylphenidate: "methylphenidate",
  atomoxetine: "atomoxetine",
  guanfacine: "atomoxetine",
  viloxazine: "atomoxetine",
};

function sanitize(text) {
  let t = String(text ?? "").replace(/\r/g, "").trim();
  if (/^(-{3,}|#)/.test(t)) t = "\\" + t;
  return t;
}

function sectionsByKind(sections, kind) {
  return sections.filter((s) => s.kind === kind);
}

function buildDoc(key) {
  const label = labels.find((l) => l.key === key);
  const drug = fda.find((d) => d.key === key);
  const tDrug = trials.drugs.find((d) => d.key === key);
  const collKey = COLLECTION_FOR[key];

  const name = drug?.name || label?.name || key;
  const brands = label?.brands || drug?.applications?.[0]?.brands?.join(", ") || "";
  const brandShort = brands.split(",")[0]?.trim().split(" ")[0] || name;
  const title = name.replace(/ dimesylate| hydrochloride/, "");

  const byNct = Object.fromEntries(trials.trials.map((t) => [t.nctid, t]));
  const drugTrials = (tDrug?.nctids || []).map((n) => byNct[n]).filter(Boolean);

  const phaseCounts = {};
  for (const t of drugTrials)
    for (const p of t.phases || [])
      phaseCounts[PHASE_LABEL[p] || p] = (phaseCounts[PHASE_LABEL[p] || p] || 0) + 1;

  const collStudies = studies.studies.filter((s) => s.collection === collKey);
  const designCounts = {};
  for (const s of collStudies)
    designCounts[s.design] = (designCounts[s.design] || 0) + 1;

  const firstApproval = drug?.applications
    ?.map((a) => a.first_approval)
    .filter(Boolean)
    .sort()[0];

  let md = "";
  md += `---\n`;
  md += `title: ${title}\n`;
  md += `subtitle: ${title} (${brandShort}) - approved indications, dosage, FDA approval history, trials and indexed evidence.\n`;
  md += `slug: ${key}\n`;
  md += `---\n\n`;

  md += `${name} is one of the medications indexed by the Clinical Evidence Index. The record consolidates FDA labeling from DailyMed, approval history from Drugs@FDA, ClinicalTrials.gov registrations, and indexed PubMed literature.\n\n`;

  md += `## At a glance\n\n`;
  const glance = [];
  if (brands) glance.push(`**Brands** - ${brands}`);
  if (firstApproval) glance.push(`**First US approval** - ${fmtDate(firstApproval)}`);
  if (drug)
    glance.push(
      `**Applications** - ${drug.applications.length} FDA application${drug.applications.length > 1 ? "s" : ""}, ${drug.generic_count} approved generic sponsor${drug.generic_count === 1 ? "" : "s"}`,
    );
  glance.push(`**Clinical trials** - ${drugTrials.length} ClinicalTrials.gov registrations`);
  glance.push(
    `**Indexed research** - ${collStudies.length} PubMed records in the [studies index](${BROWSE_HREF})`,
  );
  md += glance.map((g) => `- ${g}`).join("\n") + "\n\n";

  if (label) {
    const boxed = sectionsByKind(label.sections, "Boxed warning");
    if (boxed.length) {
      md += `## Boxed warning\n\n`;
      for (const s of boxed) {
        md += `**${sanitize(s.title)}**\n\n${sanitize(s.text)}\n\n`;
      }
      md += ``;
    }

    const ind = sectionsByKind(label.sections, "Indications and usage");
    if (ind.length) {
      md += `## Indications and usage\n\n`;
      for (const s of ind) md += `${sanitize(s.text)}\n\n`;
    }

    const dosage = sectionsByKind(label.sections, "Dosage detail");
    if (dosage.length) {
      md += `## Dosage and administration\n\n`;
      for (const s of dosage) {
        md += `### ${sanitize(s.title).replace(/^Dosage/, "Dosage")}\n\n${sanitize(s.text)}\n\n`;
      }
      md += ``;
    }

    const forms = sectionsByKind(label.sections, "Dosage forms and strengths");
    if (forms.length) {
      md += `## Forms and strengths\n\n`;
      for (const s of forms) md += `${sanitize(s.text)}\n\n`;
    }

    const safetyKinds = [
      "Contraindications",
      "Controlled substance",
      "Abuse",
      "Dependence",
      "Pregnancy",
      "Lactation",
      "Pediatric use",
      "Geriatric use",
    ];
    const safety = label.sections.filter((s) => safetyKinds.includes(s.kind));
    if (safety.length) {
      md += `## Safety and special populations\n\n`;
      for (const s of safety) {
        md += `### ${s.kind}\n\n${sanitize(s.text)}\n\n`;
      }
    }
  }

  if (drug && drug.applications.length) {
    md += `## FDA approval history\n\n`;
    md += `| Application | Sponsor | Brands | First approval | Latest action |\n`;
    md += `| --- | --- | --- | --- | --- |\n`;
    for (const a of drug.applications) {
      md += `| [${a.application}](${a.url}) | ${a.sponsor.toLowerCase()} | ${(a.brands || []).join(", ")} | ${fmtDate(a.first_approval)} | ${fmtDate(a.latest_action)} |\n`;
    }
    md += `\n`;

    const subs = (drug.applications[0]?.submissions || [])
      .filter((s) => s.status === "AP" && s.date)
      .sort((a, b) => String(b.date).localeCompare(String(a.date)))
      .slice(0, 10);
    if (subs.length) {
      md += `### Recent approved actions\n\n`;
      md += `| Action | Category | Date |\n| --- | --- | --- |\n`;
      for (const s of subs) {
        const label2 = [s.type, s.number].filter(Boolean).join(" ");
        const doc = (s.docs || []).find((d) => d.type === "Label");
        const action = doc ? `[${label2}](${doc.url})` : label2;
        md += `| ${action} | ${s.category || ""} | ${fmtDate(s.date)} |\n`;
      }
      md += `\n`;
    }
  }

  if (drugTrials.length) {
    md += `## Clinical trials\n\n`;
    md += `${drugTrials.length} registrations for this drug on ClinicalTrials.gov, by phase - [browse the trial feed](${TRIALS_HREF}).\n\n`;
    md += `| Phase | Registrations |\n| --- | --- |\n`;
    for (const [phase, n] of Object.entries(phaseCounts).sort((a, b) => b[1] - a[1])) {
      md += `| ${phase} | ${n} |\n`;
    }
    md += `\n`;
  }

  if (collStudies.length) {
    md += `## Published research\n\n`;
    md += `${collStudies.length} indexed PubMed records cover this medication, by study design - [browse the index](${BROWSE_HREF}).\n\n`;
    md += `| Study design | Records |\n| --- | --- |\n`;
    for (const [design, n] of Object.entries(designCounts).sort((a, b) => b[1] - a[1]).slice(0, 8)) {
      md += `| ${design} | ${n} |\n`;
    }
    md += `\n`;
  }

  if (label?.url) {
    md += `## Source label\n\n`;
    md += `- [Full prescribing information on DailyMed](${label.url}) (setid ${label.setid}, published ${label.published})\n`;
    if (drug) md += `- [Drugs@FDA approval record](${drug.applications[0]?.url || "https://www.accessdata.fda.gov/scripts/cder/daf/"})\n`;
    md += `\n`;
  }

  return md;
}

rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });

let index = `---\ntitle: Medications\nsubtitle: One doc page per medication - label, approval history, trials and evidence.\nslug: medications\n---\n\n`;

for (const key of trials.drugs.map((d) => d.key)) {
  const md = buildDoc(key);
  writeFileSync(path.join(OUT, `${key}.mdx`), md);
  const title = md.match(/^title: (.+)$/m)?.[1] || key;
  const subtitle = md.match(/^subtitle: (.+)$/m)?.[1] || "";
  index += `- **[${title}](${"/" + key})** - ${subtitle.replace(/\.$/, "")}.\n`;
  console.log(`wrote content/docs/${key}.mdx (${md.length} chars)`);
}

writeFileSync(path.join(OUT, "medications.mdx"), index);
console.log("wrote content/docs/medications.mdx");
