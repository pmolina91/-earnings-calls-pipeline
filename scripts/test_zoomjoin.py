#!/usr/bin/env python3
"""Teste do fluxo completo Zoom: registrar -> extrair tk -> entrar na SALA (web client).
Sucesso = chegar na tela do webinar ("aguardando o organizador"/player), NAO na pagina de registro.
Auto-diagnostico: commita estado+screenshot de cada passo."""
import json, sys, os, time, re, subprocess
from playwright.sync_api import sync_playwright
sys.path.insert(0, 'scripts')
from registration import try_register

spec = json.load(open(sys.argv[1]))
NAME = os.environ.get('REG_NAME','Philippe Molina'); EMAIL = os.environ.get('REG_EMAIL','')
COMPANY = os.environ.get('REG_COMPANY',''); PHONE = os.environ.get('REG_PHONE','')
RID = os.environ.get('GITHUB_RUN_ID','local')
os.makedirs('logs', exist_ok=True); os.makedirs('work/shots', exist_ok=True)
passos = []

def snap(page, nome):
    try:
        page.screenshot(path=f'work/shots/{nome}.png', full_page=False)
    except Exception: pass
    try:
        body = (page.evaluate('() => document.body.innerText') or '')[:500].replace('\n',' | ')
    except Exception:
        body = 'ERRO_LEITURA'
    passos.append(f"== {nome} ==\nurl: {page.url[:150]}\ntexto: {body}\n")
    print(f'[{nome}] {page.url[:100]}', flush=True)

with sync_playwright() as pw:
    b = pw.chromium.launch(args=[
        '--autoplay-policy=no-user-gesture-required',
        '--use-fake-ui-for-media-stream',
        '--enable-features=SharedArrayBuffer',
        '--disable-blink-features=AutomationControlled',
    ])
    ctx = b.new_context(locale='pt-BR',
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
    page = ctx.new_page()
    page.goto(spec['register_url'], timeout=90000, wait_until='domcontentloaded'); time.sleep(6)
    snap(page, '1_registro')
    log = try_register(page, NAME, EMAIL, COMPANY, PHONE, 'Buy side'); time.sleep(8)
    passos.append('acoes_registro: ' + ', '.join(log))
    snap(page, '2_pos_registro')
    # extrair tk e id
    tk = None; wid = None
    m = re.search(r'[?&]tk=([^&#]+)', page.url)
    if m: tk = m.group(1)
    join = page.evaluate('''() => { const a=[...document.querySelectorAll('a')].find(x=>/zoom.us\\/(w|wc)\\//.test(x.href)); return a?a.href:null }''')
    m2 = re.search(r'/w/(\d+)', join or '')
    if m2: wid = m2.group(1)
    if not wid:
        body = page.evaluate('() => document.body.innerText') or ''
        m3 = re.search(r'(\d{3})[ .-]?(\d{4})[ .-]?(\d{4})', body)
        if m3: wid = ''.join(m3.groups())
    passos.append(f'extraidos: tk={"sim" if tk else "NAO"} wid={wid} join_link={join[:100] if join else "NAO"}')
    host = re.match(r'https://[^/]+', page.url).group(0)
    candidatos = []
    if join: candidatos.append(('link_pagina', join))
    if wid: candidatos.append(('wc_montado', f"{host}/wc/{wid}/join" + (f"?tk={tk}" if tk else '')))
    sucesso = False
    for rotulo, alvo in candidatos:
        try:
            page.goto(alvo, timeout=90000, wait_until='domcontentloaded'); time.sleep(12)
            snap(page, f'3_join_{rotulo}')
            # se caiu em pagina "Launch Meeting", clicar em "join from browser"
            try:
                a = page.locator('a:has-text("browser"), a:has-text("navegador")').first
                if a.is_visible(timeout=3000):
                    a.click(); time.sleep(12); snap(page, f'4_wc_{rotulo}')
            except Exception: pass
            # preencher nome/email se o web client pedir
            try:
                for sel, val in [('#input-for-name', NAME), ('input[type=text]', NAME), ('#input-for-email', EMAIL), ('input[type=email]', EMAIL)]:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000): el.fill(val)
                page.locator('button:has-text("Entrar"), button:has-text("Join"), button:has-text("Ingressar")').first.click(timeout=4000)
                time.sleep(15)
            except Exception: pass
            snap(page, f'5_final_{rotulo}')
            body = (page.evaluate('() => document.body.innerText') or '').lower()
            em_sala = any(s in body for s in ['aguardando', 'waiting for', 'has not started', 'ainda não começou', 'nao comecou', 'começará em', 'audio', 'áudio', 'leave', 'sair'])
            em_registro = 'registration' in page.url or 'inscri' in body[:300]
            passos.append(f'veredito_{rotulo}: em_sala={em_sala} em_registro={em_registro} url={page.url[:120]}')
            if em_sala and not em_registro:
                sucesso = True; break
        except Exception as e:
            passos.append(f'ERRO_{rotulo}: {str(e)[:200]}')
    b.close()

open(f'logs/ZOOMJOIN_{RID}.txt','w').write(('SUCESSO\n' if sucesso else 'FALHOU\n') + '\n'.join(passos))
# screenshots pequenos no repo (diagnostico visual)
subprocess.run(['bash','-c', f'mkdir -p logs/shots_{RID} && cp work/shots/*.png logs/shots_{RID}/ 2>/dev/null || true'])
print('SUCESSO' if sucesso else 'FALHOU')
