#!/usr/bin/env python3
"""Descobre a URL do player de webcast a partir da pagina de RI (segue links de eventos/webcast).
Dump: candidatos que casam choruscall/mediaframe/webcast/edge.media/q4/veracast/videonewswire.
Uso: python3 scripts/find_webcast_url.py <start_url> [extra_url ...]"""
import sys, time, re, json
from playwright.sync_api import sync_playwright

PAT = re.compile(r'(choruscall|mediaframe|webcast|edge\.media|q4cdn|q4inc|veracast|video.*newswire|onlinexperiences|streamerlive)', re.I)
starts = sys.argv[1:] or ['https://ir.tyson.com']
found = {}
net = set()

def collect(page):
    try:
        links = page.evaluate('()=>[...document.querySelectorAll("a[href]")].map(a=>({href:a.href, txt:(a.innerText||a.getAttribute("aria-label")||"").trim().slice(0,60)}))')
    except Exception:
        links = []
    return links

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
    ctx = b.new_context(locale='en-US'); p = ctx.new_page()
    p.on('request', lambda r: net.add(r.url) if PAT.search(r.url) else None)
    to_visit = list(starts)
    visited = set()
    # tambem tenta caminhos comuns de eventos
    guesses = ['https://ir.tyson.com/events-and-presentations/default.aspx',
               'https://ir.tyson.com/news-and-events/events/default.aspx',
               'https://ir.tyson.com/events/default.aspx']
    to_visit += guesses
    for url in to_visit[:8]:
        if url in visited: continue
        visited.add(url)
        try:
            p.goto(url, timeout=60000, wait_until='domcontentloaded'); time.sleep(6)
        except Exception as e:
            found.setdefault('_errors', []).append(f'{url}: {str(e)[:80]}'); continue
        links = collect(p)
        for l in links:
            if PAT.search(l['href']) or re.search(r'webcast|replay|listen|earnings|results', (l['txt'] or ''), re.I):
                found.setdefault(url, []).append(l)
        # segue 1 nivel: links de eventos/webcast
        for l in links:
            if re.search(r'event|webcast|presentation|results|earnings', (l['href']+' '+(l['txt'] or '')), re.I) and l['href'] not in visited and 'tyson.com' in l['href']:
                to_visit.append(l['href'])
    b.close()

out = {'net_matches': sorted(net), 'link_candidates': found}
print(json.dumps(out, indent=1, ensure_ascii=False)[:6000])
