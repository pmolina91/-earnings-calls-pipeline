#!/usr/bin/env python3
"""Descobre a URL do formulário de mailing/cadastro de cada RI (navegador real)."""
import json, sys, os, time, re
from playwright.sync_api import sync_playwright
spec = json.load(open(sys.argv[1]))
out = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(args=['--no-sandbox'])
    ctx = b.new_context(locale='pt-BR')
    for emp in spec['empresas']:
        t = emp['ticker']
        try:
            p = ctx.new_page()
            p.goto(emp['url'], timeout=40000, wait_until='domcontentloaded'); time.sleep(6)
            urls = p.evaluate('''() => [...new Set([...document.querySelectorAll('a')]
                .filter(a=>/mailing|cadastr|newsletter|e-?mail.?alert|alerta/i.test(a.href + ' ' + (a.innerText||'')))
                .map(a=>a.href))].slice(0,3)''')
            tem_form = p.evaluate('''() => !!document.querySelector('input[type=email]')''')
            out[t] = {'mailing_urls': urls, 'form_na_home': tem_form}
            p.close()
        except Exception as e:
            out[t] = {'erro': str(e)[:100]}
        print(t, out[t], flush=True)
    b.close()
os.makedirs('work', exist_ok=True)
json.dump(out, open('work/mailing_urls.json','w'), indent=1, ensure_ascii=False)
