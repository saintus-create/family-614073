import { readFileSync } from "fs";
import path from "path";

// Data lives in the repo's single source of truth: fern/data/*.json
const DATA_DIR = path.join(process.cwd(), "..", "fern", "data");

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function readData(name: string): any {
  return JSON.parse(readFileSync(path.join(DATA_DIR, name), "utf8"));
}

export function studies() {
  return readData("studies.json");
}

export function trials() {
  return readData("trials.json");
}

export function labels() {
  return readData("labels.json");
}

export function fda() {
  return readData("fda.json");
}

export function coverage() {
  return readData("coverage.json");
}

export function publicHealth() {
  return readData("public_health.json");
}

export const PHASE_LABEL: Record<string, string> = {
  EARLY_PHASE1: "Early Phase 1",
  PHASE1: "Phase 1",
  PHASE2: "Phase 2",
  PHASE3: "Phase 3",
  PHASE4: "Phase 4",
  NA: "Not applicable",
};

export const STATUS_LABEL: Record<string, string> = {
  RECRUITING: "Recruiting",
  NOT_YET_RECRUITING: "Not yet recruiting",
  ACTIVE_NOT_RECRUITING: "Active, not recruiting",
  COMPLETED: "Completed",
  TERMINATED: "Terminated",
  WITHDRAWN: "Withdrawn",
  SUSPENDED: "Suspended",
  UNKNOWN: "Unknown status",
  ENROLLING_BY_INVITATION: "Enrolling by invitation",
};
