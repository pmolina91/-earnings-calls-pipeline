#!/usr/bin/env python3
"""Dry-run de registro: abre a URL, registra com a identidade, tira screenshots antes/depois."""
import json, sys, os, time
from playwright.sync_api import sync_playwright
from registration import try_register

url = json.load(open(sys.argv[1]))['register_url']
os.makedirs('work/shots', exist_ok=True)
with sync_playwright() as pw:
    b = pw.chromium.launch()
    page = b.new_context(locale='pt-BR').new_page()
    page.goto(url, timeout=90000, wait_until='domcontentloaded')
    time.sleep(6)
    page.screenshot(path='work/shots/1_antes.png', full_page=True)
    log = try_register(page, os.environ['REG_NAME'], os.environ['REG_EMAIL'], os.environ['REG_COMPANY'])
    time.sleep(6)
    page.screenshot(path='work/shots/2_depois.png', full_page=True)
    body = page.inner_text('body')[:3000]
    ok = any(k in body.lower() for k in ['confirm', 'registrado', 'aprovada', 'inscri', 'adicionar ao calend', 'you are registered', 'e-mail de confirma'])
    # sanitizar identidade antes de qualquer saída que vá para repo público
    red = body
    for v in [os.environ.get('REG_NAME',''), os.environ.get('REG_EMAIL',''), os.environ.get('REG_COMPANY','')]:
        if v: red = red.replace(v, '***')
        if v and ' ' in v:
            for parte in v.split():
                red = red.replace(parte, '***')
    open('work/shots/resultado.txt','w').write(
        'ACOES: ' + ', '.join(log) + f'\nCONFIRMACAO_DETECTADA: {ok}\nURL_FINAL: ' + page.url + '\n\nPAGINA FINAL (sanitizada):\n' + red)
    print('ACOES:', log)
    print('CONFIRMACAO_DETECTADA:', ok)
    b.close()
