from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "fern" / "docs" / "pages"
DOCS = ROOT / "fern" / "docs.yml"

slugs = set()
for page in PAGES.rglob("*.mdx"):
    source = page.read_text(errors="ignore")
    match = re.search(r"^slug:\s*[\"']?([^\n\"']+)", source, re.M)
    if match:
        slugs.add("/" + match.group(1).strip("/"))

missing_links = []
for page in PAGES.rglob("*.mdx"):
    source = page.read_text(errors="ignore")
    for match in re.finditer(r"\]\((/[^)#? ]+)", source):
        link = match.group(1).rstrip("/") or "/"
        if link not in slugs and link not in {"/docs"}:
            missing_links.append((page, link))

missing_nav = []
for match in re.finditer(r"^\s+path:\s+([^\n]+)$", DOCS.read_text(), re.M):
    path = match.group(1).strip()
    if not (ROOT / "fern" / path).exists():
        missing_nav.append(("(navigation entry)", path))

print("INTERNAL_LINK_MISSING", len(missing_links))
for page, link in missing_links[:100]:
    print(f"  {page}: {link}")
print("NAV_PATH_MISSING", len(missing_nav))
for page, path in missing_nav[:100]:
    print(f"  {page}: {path}")
raise SystemExit(1 if missing_links or missing_nav else 0)
