import { readFileSync, readdirSync, statSync } from "fs";
import path from "path";

const FERN_PAGES = path.join(process.cwd(), "..", "fern", "docs", "pages");
const DOC_PAGES = path.join(process.cwd(), "content", "docs");

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (name.endsWith(".mdx") || name.endsWith(".md")) out.push(full);
  }
  return out;
}

function frontmatter(raw: string): Record<string, string> {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  const fm: Record<string, string> = {};
  if (!m) return fm;
  for (const line of m[1].split(/\r?\n/)) {
    const kv = line.match(/^(\w[\w-]*):\s*(.*)$/);
    if (kv) fm[kv[1]] = kv[2].replace(/^["']|["']$/g, "").trim();
  }
  return fm;
}

export function pageMap(): Map<string, string> {
  const map = new Map<string, string>();

  for (const file of walk(FERN_PAGES)) {
    const raw = readFileSync(file, "utf8");
    const fm = frontmatter(raw);
    const slug = fm.slug || path.basename(file).replace(/\.mdx?$/, "");
    if (!map.has(slug)) map.set(slug, file);
  }

  try {
    for (const file of walk(DOC_PAGES)) {
      const raw = readFileSync(file, "utf8");
      const fm = frontmatter(raw);
      const slug = fm.slug || path.basename(file).replace(/\.mdx?$/, "");
      map.set(slug, file);
    }
  } catch {
    // content/docs may not exist yet
  }

  return map;
}

export function allSlugs(): string[] {
  return [...pageMap().keys()].sort();
}

function decodeAttribute(value: string): string {
  return value
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

function getAttribute(attrs: string, name: string): string {
  const quoted = attrs.match(new RegExp(`${name}="([^"]*)"`));
  if (quoted) return decodeAttribute(quoted[1]);
  const single = attrs.match(new RegExp(`${name}='([^']*)'`));
  if (single) return decodeAttribute(single[1]);
  return "";
}

function headingLink(title: string, href: string): string {
  const label = title || href;
  return href ? `### [${label}](${href})` : `### ${label}`;
}

function asBlockquote(body: string): string {
  return body
    .trim()
    .split(/\r?\n/)
    .map((line) => (line.trim() ? `> ${line.trim()}` : ">"))
    .join("\n");
}

function flattenFernMdx(raw: string): string {
  let out = raw;

  out = out.replace(/<Icon\b[^>]*\/?>/g, "");

  out = out.replace(/<Badge\b[^>]*>([\s\S]*?)<\/Badge>/g, (_m, body) => {
    const text = String(body).trim();
    return text ? `**${text}**` : "";
  });

  out = out.replace(/<Button\b([^>]*)>([\s\S]*?)<\/Button>/g, (_m, attrs, body) => {
    const href = getAttribute(attrs, "href");
    const label = String(body).trim() || href;
    return href ? `[${label}](${href})` : label;
  });

  out = out.replace(/<Callout\b[^>]*>([\s\S]*?)<\/Callout>/g, (_m, body) => {
    return `\n${asBlockquote(String(body))}\n`;
  });

  out = out.replace(/<Accordion\b([^>]*)>([\s\S]*?)<\/Accordion>/g, (_m, attrs, body) => {
    const title = getAttribute(attrs, "title") || "Details";
    return `\n<details>\n<summary>${title}</summary>\n\n${String(body).trim()}\n\n</details>\n`;
  });

  out = out.replace(/<Card\b([^>]*)>([\s\S]*?)<\/Card>/g, (_m, attrs, body) => {
    const title = getAttribute(attrs, "title");
    const href = getAttribute(attrs, "href");
    const text = String(body).trim();
    return `\n${headingLink(title, href)}${text ? `\n\n${text}` : ""}\n`;
  });

  out = out.replace(/<Step\b([^>]*)>([\s\S]*?)<\/Step>/g, (_m, attrs, body) => {
    const title = getAttribute(attrs, "title");
    return `\n${title ? `### ${title}\n\n` : ""}${String(body).trim()}\n`;
  });

  out = out.replace(/<Tab\b([^>]*)>/g, (_m, attrs) => {
    const title = getAttribute(attrs, "title");
    return title ? `\n### ${title}\n\n` : "\n";
  });

  out = out.replace(/<\/Tab>/g, "\n");
  out = out.replace(/<\/?(?:CardGroup|AccordionGroup|Steps|Tabs)\b[^>]*>/g, "\n");

  return out;
}

function mdxSafe(raw: string): string {
  return flattenFernMdx(raw)
    .replace(/<(?![A-Za-z/])/g, "&lt;")
    .replace(/(?<!=\s*)\{/g, "&#123;");
}

export function readPage(
  slug: string,
): { source: string; file: string } | null {
  const map = pageMap();
  const file = map.get(slug);
  if (!file) return null;
  return { source: mdxSafe(readFileSync(file, "utf8")), file };
}
