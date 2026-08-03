#!/usr/bin/env python3
"""Descobre a URL do player de webcast a partir do site de RI (SPA pesado).
Varre o HTML RENDERIZADO inteiro (nao so <a href>) + XHR por URLs de webcast/choruscall.
Uso: python3 scripts/find_webcast_url.py <start_url>"""
import sys, time, re, json
from playwright.sync_api import sync_playwright

URL_RE = re.compile(r'https?://[^\s"\'<>()]+', re.I)
PAT = re.compile(r'(choruscall|mediaframe|webcast|edge\.media|q4cdn|q4inc|veracast|videonewswire|onlinexperiences|streamerlive|issuerdirect|webcasts?\.com|open\.exchange)', re.I)
start = sys.argv[1] if len(sys.argv) > 1 else 'https://ir.tyson.com'
hits = set(); net = set(); errors = []; visited = set()

def scan(page):
    try:
        html = page.content()
    except Exception:
        html = ''
    for u in URL_RE.findall(html):
        if PAT.search(u): hits.add(u.rstrip('\\').strip('",);'))
    # tambem texto de scripts/data-attrs via evaluate
    try:
        extra = page.evaluate('()=>document.documentElement.outerHTML') or ''
        for u in URL_RE.findall(extra):
            if PAT.search(u): hits.add(u.rstrip('\\').strip('",);'))
    except Exception: pass

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
    ctx = b.new_context(locale='en-US'); p = ctx.new_page()
    p.on('request', lambda r: net.add(r.url) if PAT.search(r.url) else None)
    p.on('response', lambda r: net.add(r.url) if PAT.search(r.url) else None)
    candidates = [start,
                  'https://ir.tyson.com/events-and-presentations/default.aspx',
                  'https://ir.tyson.com/news-events/events/default.aspx',
                  'https://ir.tyson.com/news-events/events-and-presentations/default.aspx',
                  'https://ir.tyson.com/investors/events-and-presentations/default.aspx']
    for url in candidates:
        if url in visited: continue
        visited.add(url)
        try:
            p.goto(url, timeout=70000, wait_until='domcontentloaded')
            try: p.wait_for_load_state('networkidle', timeout=15000)
            except Exception: pass
            time.sleep(6)
        except Exception as e:
            errors.append(f'{url}: {str(e)[:90]}'); continue
        scan(p)
        # segue links de nav que contenham event/webcast/presentation
        try:
            navlinks = p.evaluate('''()=>[...document.querySelectorAll('a[href]')].map(a=>a.href).filter(h=>/event|webcast|presentation|news-events/i.test(h) && h.includes('tyson.com'))''')
        except Exception:
            navlinks = []
        for h in navlinks[:4]:
            if h in visited: continue
            visited.add(h)
            try:
                p.goto(h, timeout=60000, wait_until='domcontentloaded')
                try: p.wait_for_load_state('networkidle', timeout=12000)
                except Exception: pass
                time.sleep(5); scan(p)
            except Exception as e:
                errors.append(f'{h}: {str(e)[:80]}')
    b.close()

print(json.dumps({'webcast_hits': sorted(hits), 'net_matches': sorted(net), 'errors': errors, 'visited': sorted(visited)}, indent=1, ensure_ascii=False)[:6000])
