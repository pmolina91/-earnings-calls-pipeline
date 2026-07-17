#!/usr/bin/env python3
"""Varredura de RIs com navegador real (Playwright): renderiza JS, lê widgets/modais
de calendário e extrai datas + links de webcast/.ics. Uso: scan_ri.py <spec.json>
Spec: {"empresas": [{"ticker": "X", "urls": ["https://...", ...]}]}
Saída: logs/SCAN_RI_<runid>.json (via workflow)."""
import json, sys, os, re, time, traceback
from playwright.sync_api import sync_playwright

spec = json.load(open(sys.argv[1]))
out = {}
KEY = re.compile(r'(2T26|1T27|divulga|resultado|webcast|teleconfer|confer[eê]ncia|calend)', re.I)

with sync_playwright() as pw:
    browser = pw.chromium.launch(args=['--no-sandbox'])
    ctx = browser.new_context(locale='pt-BR')
    for emp in spec['empresas']:
        t = emp['ticker']; out[t] = {'trechos': [], 'links': [], 'erros': []}
        for url in emp['urls']:
            try:
                page = ctx.new_page()
                page.goto(url, timeout=45000, wait_until='domcontentloaded')
                time.sleep(8)
                body = page.inner_text('body')
                # janelas de texto ao redor de datas/palavras-chave
                for m in re.finditer(r'.{0,200}(2T26|Divulgação de Resultados|Webcast|Teleconferência).{0,300}', body):
                    tr = re.sub(r'\s+', ' ', m.group(0)).strip()
                    if KEY.search(tr) and re.search(r'\d{1,2}', tr) and tr not in out[t]['trechos']:
                        out[t]['trechos'].append(tr[:400])
                links = page.evaluate('''() => [...document.querySelectorAll('a')].map(a => ({t:(a.innerText||a.getAttribute('aria-label')||'').trim().slice(0,50), h:a.href})).filter(l => /\\.ics|calendar\\.google|outlook|zoom|webcast|register|mailerurl/i.test(l.h)).slice(0,10)''')
                for l in links:
                    if l not in out[t]['links']: out[t]['links'].append(l)
                page.close()
            except Exception as e:
                out[t]['erros'].append(f'{url}: {str(e)[:120]}')
        out[t]['trechos'] = out[t]['trechos'][:6]
        print(t, '| trechos:', len(out[t]['trechos']), '| links:', len(out[t]['links']), flush=True)
    browser.close()
os.makedirs('work', exist_ok=True)
json.dump(out, open('work/scan_ri.json','w'), indent=1, ensure_ascii=False)
