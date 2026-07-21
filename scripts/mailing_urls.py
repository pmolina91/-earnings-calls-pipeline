#!/usr/bin/env python3
"""Descobre a URL do formulário de mailing/cadastro de cada RI (navegador real).
v2: crawl 2 níveis — home + páginas candidatas (serviços/contato/atendimento/outras infos)."""
import json, sys, os, time, re
from playwright.sync_api import sync_playwright

spec = json.load(open(sys.argv[1]))
out = {}

if spec.get('probe_paths'):
    PATHS = spec['probe_paths']
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=['--no-sandbox'])
        ctx = b.new_context(locale='pt-BR', ignore_https_errors=True)
        for emp in spec['empresas']:
            t = emp['ticker']; base = emp['url'].rstrip('/')
            hits = []
            p = ctx.new_page()
            for path in PATHS:
                if len(hits) >= 2: break
                u = base + path
                try:
                    r = p.goto(u, timeout=25000, wait_until='domcontentloaded'); time.sleep(3)
                    if r and r.status < 400 and 'nao-encontrada' not in p.url and 'not-found' not in p.url:
                        f = p.evaluate('() => ({email: !!document.querySelector("input[type=email], input[name*=mail i], input[id*=mail i]"), t: document.title})')
                        if f['email'] and not re.search(r'não encontrada|nao encontrada|not found|404', f['t'], re.I):
                            hits.append(p.url)
                except Exception:
                    pass
            out[t] = {'probe_hits': hits}
            print(t, hits, flush=True)
            p.close()
        b.close()
    os.makedirs('work', exist_ok=True)
    json.dump(out, open('work/mailing_urls.json','w'), indent=1, ensure_ascii=False)
    sys.exit(0)

FIND_LINKS = '''() => [...new Set([...document.querySelectorAll('a')]
    .filter(a=>/mailing|cadastr|newsletter|e-?mail.?alert|alerta/i.test(a.href + ' ' + (a.innerText||'')))
    .map(a=>a.href))].slice(0,5)'''
FIND_SECTIONS = '''() => [...new Set([...document.querySelectorAll('a')]
    .filter(a=>/servi|contat|atendimento|outras|investidor|acionista|fale/i.test(a.href + ' ' + (a.innerText||'')))
    .map(a=>a.href))].filter(h=>h.startsWith('http')).slice(0,12)'''
HAS_FORM = '''() => ({email: !!document.querySelector("input[type=email], input[name*=mail i], input[id*=mail i]"),
    inputs: document.querySelectorAll('input').length})'''

with sync_playwright() as pw:
    b = pw.chromium.launch(args=['--no-sandbox'])
    ctx = b.new_context(locale='pt-BR')
    for emp in spec['empresas']:
        t = emp['ticker']
        res = {'mailing_urls': [], 'form_urls': [], 'form_na_home': False}
        try:
            p = ctx.new_page()
            p.goto(emp['url'], timeout=40000, wait_until='domcontentloaded'); time.sleep(6)
            res['mailing_urls'] = p.evaluate(FIND_LINKS)
            res['form_na_home'] = p.evaluate(HAS_FORM)['email']
            secoes = [] if res['mailing_urls'] else p.evaluate(FIND_SECTIONS)
            # nivel 2: visita candidatos ate achar link/form de mailing
            for u in (res['mailing_urls'][:2] or []) + secoes[:8]:
                if len(res['form_urls']) >= 2: break
                try:
                    p.goto(u, timeout=30000, wait_until='domcontentloaded'); time.sleep(4)
                    f = p.evaluate(HAS_FORM)
                    l2 = p.evaluate(FIND_LINKS)
                    if f['email'] and re.search(r'mailing|cadastr|alerta|contat', p.url, re.I):
                        res['form_urls'].append(p.url)
                    for x in l2:
                        if x not in res['mailing_urls']: res['mailing_urls'].append(x)
                except Exception:
                    pass
            # se achou link de mailing no nivel 2 mas ainda sem form_url, testa o primeiro
            if res['mailing_urls'] and not res['form_urls']:
                for u in res['mailing_urls'][:3]:
                    try:
                        p.goto(u, timeout=30000, wait_until='domcontentloaded'); time.sleep(4)
                        if p.evaluate(HAS_FORM)['email']:
                            res['form_urls'].append(p.url); break
                    except Exception:
                        pass
            out[t] = res
            p.close()
        except Exception as e:
            out[t] = {'erro': str(e)[:100]}
        print(t, json.dumps(out[t], ensure_ascii=False)[:200], flush=True)
    b.close()
os.makedirs('work', exist_ok=True)
json.dump(out, open('work/mailing_urls.json','w'), indent=1, ensure_ascii=False)

# --- modo probe: testa caminhos padrao por dominio (spec['probe_paths']) ---
