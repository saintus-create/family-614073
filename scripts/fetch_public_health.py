#!/usr/bin/env python3
"""Harvest US federal public-health ADHD guidance into fern/data/public_health.json.

CDC and NIMH material is US Government work in the public domain, so the text
is reproduced verbatim rather than summarised. Used for the myths/issues pages.
"""
import html
import json
import pathlib
import re
import time
import shutil
import subprocess
import urllib.request

OUT = (pathlib.Path(__file__).resolve().parent.parent
       / 'fern' / 'data' / 'public_health.json')

PAGES = [
    ('cdc-about', 'CDC', 'About ADHD',
     'https://www.cdc.gov/adhd/about/index.html'),
    ('cdc-symptoms', 'CDC', 'ADHD symptoms',
     'https://www.cdc.gov/adhd/signs-symptoms/index.html'),
    ('cdc-diagnosis', 'CDC', 'Diagnosing ADHD',
     'https://www.cdc.gov/adhd/diagnosis/index.html'),
    ('cdc-treatment', 'CDC', 'Treatment of ADHD',
     'https://www.cdc.gov/adhd/treatment/index.html'),
    ('cdc-data', 'CDC', 'ADHD data and statistics',
     'https://www.cdc.gov/adhd/data/index.html'),
    ('cdc-adults', 'CDC', 'ADHD in adults',
     'https://www.cdc.gov/adhd/adults/index.html'),
    ('nimh-adhd', 'NIMH', 'Attention-Deficit/Hyperactivity Disorder',
     'https://www.nimh.nih.gov/health/topics/'
     'attention-deficit-hyperactivity-disorder-adhd'),
    ('nimh-adhd-adults', 'NIMH', 'Could I have ADHD?',
     'https://www.nimh.nih.gov/health/publications/could-i-have-adhd'),
    ('nimh-adhd-children', 'NIMH', 'ADHD in children and teens: what you need to know',
     'https://www.nimh.nih.gov/health/publications/'
     'attention-deficit-hyperactivity-disorder-in-children-and-teens-'
     'what-you-need-to-know'),
]

DROP = re.compile(
    r'^(share|print|related pages|on this page|last reviewed|sources?|references?|'
    r'view all|learn more|for more information|español|skip to|back to top|'
    r'page last|content source|get email updates|footer|follow us)\b', re.I)


def fetch(url, tries=3):
    """CDC rejects urllib's handshake, so shell out to curl where available."""
    for i in range(tries):
        if shutil.which('curl'):
            # cdc.gov's WAF rejects browser user-agents from this network but
            # serves curl's default agent, so send no custom UA.
            r = subprocess.run(
                ['curl', '-sL', '--compressed', '--max-time', '60', url],
                capture_output=True, text=True)
            if r.returncode == 0 and len(r.stdout) > 2000:
                return r.stdout
        else:
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; evidence-index/1.0)'})
                with urllib.request.urlopen(req, timeout=60) as fh:
                    return fh.read().decode('utf-8', 'replace')
            except Exception:
                pass
        time.sleep(2 * (i + 1))
    print('    failed to fetch')
    return None


def strip_tags(frag):
    frag = re.sub(r'(?s)<(script|style|svg|noscript).*?</\1>', ' ', frag)
    frag = re.sub(r'(?s)<[^>]+>', ' ', frag)
    return re.sub(r'\s+', ' ', html.unescape(frag)).strip()


def parse(raw):
    """Return [{heading, level, paragraphs[], bullets[]}] preserving source text."""
    raw = re.sub(r'(?s)<(script|style|nav|header|footer|aside|form).*?</\1>', ' ', raw)
    main = re.search(r'(?s)<main\b.*?</main>', raw)
    body = main.group(0) if main else raw

    # split on headings, keeping them
    parts = re.split(r'(?s)(<h([2-4])\b[^>]*>.*?</h\2>)', body)
    sections, current = [], {'heading': None, 'level': 2,
                             'paragraphs': [], 'bullets': []}
    i = 0
    while i < len(parts):
        chunk = parts[i]
        if re.match(r'(?s)^<h([2-4])\b', chunk or ''):
            if current['paragraphs'] or current['bullets']:
                sections.append(current)
            lvl = int(re.match(r'(?s)^<h([2-4])', chunk).group(1))
            current = {'heading': strip_tags(chunk), 'level': lvl,
                       'paragraphs': [], 'bullets': []}
            i += 2  # skip the captured level group
            continue

        for p in re.findall(r'(?s)<p\b[^>]*>(.*?)</p>', chunk or ''):
            txt = strip_tags(p)
            if len(txt) > 40 and not DROP.match(txt):
                current['paragraphs'].append(txt)
        for li in re.findall(r'(?s)<li\b[^>]*>(.*?)</li>', chunk or ''):
            txt = strip_tags(li)
            # nav lists are short link labels; real content bullets are sentences
            if 25 < len(txt) < 600 and not DROP.match(txt):
                current['bullets'].append(txt)
        i += 1

    if current['paragraphs'] or current['bullets']:
        sections.append(current)

    # de-duplicate bullets that repeat the nav
    seen = set()
    for s in sections:
        s['bullets'] = [b for b in s['bullets']
                        if not (b.lower() in seen or seen.add(b.lower()))]
    return [s for s in sections if s['paragraphs'] or s['bullets']]


def main():
    out = []
    for key, agency, title, url in PAGES:
        print(f'{agency} — {title} …')
        raw = fetch(url)
        if not raw:
            continue
        sections = parse(raw)
        if not sections:
            print('    no sections parsed')
            continue
        n_p = sum(len(s['paragraphs']) for s in sections)
        n_b = sum(len(s['bullets']) for s in sections)
        out.append({'key': key, 'agency': agency, 'title': title,
                    'url': url, 'sections': sections})
        print(f'    {len(sections)} sections, {n_p} paragraphs, {n_b} bullets')
        time.sleep(0.5)

    OUT.write_text(json.dumps({'pages': out}, indent=1))
    print(f'\nWrote {OUT} — {len(out)} pages')


if __name__ == '__main__':
    main()
