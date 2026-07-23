#!/usr/bin/env python3
"""Espera até T-10min, abre o webcast, registra com a identidade (secrets) e grava o áudio
em chunks de 2min em work/audio/. Estratégia dupla:
 A) sniffing de rede: se o player expõe stream HLS/DASH (m3u8/mpd/mp3/aac), grava via ffmpeg direto.
 B) fallback: áudio da aba via PulseAudio virtual sink + ffmpeg (funciona p/ Zoom web client etc).
Sentinela work/audio/END criada ao detectar fim (silêncio prolongado pós-início ou stream fechado)."""
import json, sys, os, time, re, subprocess, threading
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

spec = json.load(open(sys.argv[1]))
os.makedirs('work/audio', exist_ok=True)
call = datetime.fromisoformat(spec['call_datetime_utc'].replace('Z','+00:00'))
wait = (call - datetime.now(timezone.utc)).total_seconds() - 600
if wait > 0:
    print(f'esperando {wait/60:.0f}min até T-10min...'); time.sleep(wait)

NAME, EMAIL, COMPANY = os.environ['REG_NAME'], os.environ['REG_EMAIL'], os.environ['REG_COMPANY']
PHONE, TITLECAT = os.environ.get('REG_PHONE',''), os.environ.get('REG_TITLE_CATEGORY','Buy side')
import sys as _sys; _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from registration import try_register as _try_register
MEDIA_RE = re.compile(r'\.(m3u8|mpd|mp3|aac)(\?|$)')
stream_url = {}

def try_register(page):
    return _try_register(page, NAME, EMAIL, COMPANY, PHONE, TITLECAT)

def record_hls(url):
    print('gravando via ffmpeg (stream direto):', url[:100])
    subprocess.run(['ffmpeg','-loglevel','warning','-i',url,'-vn','-ac','1','-ar','16000',
        '-f','segment','-segment_time','120','-reset_timestamps','1',
        'work/audio/chunk_%04d.wav'])

def record_pulse():
    print('gravando via PulseAudio (áudio da aba)')
    subprocess.run(['pulseaudio','--start','--exit-idle-time=-1'])
    subprocess.run(['pactl','load-module','module-null-sink','sink_name=cap'])
    os.environ['PULSE_SINK']='cap'
    subprocess.Popen(['ffmpeg','-loglevel','warning','-f','pulse','-i','cap.monitor','-ac','1','-ar','16000',
        '-f','segment','-segment_time','120','-reset_timestamps','1','work/audio/chunk_%04d.wav'])

with sync_playwright() as pw:
    browser = pw.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    ctx = browser.new_context(locale='pt-BR')
    page = ctx.new_page()
    page.on('request', lambda r: stream_url.setdefault('u', r.url) if MEDIA_RE.search(r.url) else None)
    if spec.get('join_url'):
        # ingresso DIRETO com link pessoal (emergencia): /w/ -> web client /wc/
        import re as _re
        ju = spec['join_url']
        m = _re.search(r'zoom.us/w/(\d+)\?(.*)', ju)
        if m:
            host = _re.match(r'https://[^/]+', ju).group(0)
            ju_wc = f"{host}/wc/{m.group(1)}/join?{m.group(2)}"
        else:
            ju_wc = ju
        print(f'[capture] JOIN DIRETO: {ju_wc[:70]}...')
        page.goto(ju_wc, timeout=90000, wait_until='domcontentloaded')
        time.sleep(15)
        try:
            a = page.locator('a:has-text("browser"), a:has-text("navegador")').first
            if a.is_visible(timeout=3000): a.click(); time.sleep(12)
        except Exception: pass
        try:
            for sel, val in [('input[type=text]', os.environ.get('REG_NAME','Philippe Molina')),
                             ('input[type=email]', os.environ.get('REG_EMAIL',''))]:
                el = page.locator(sel).first
                if el.is_visible(timeout=2500): el.fill(val)
        except Exception: pass
        try:
            page.locator('button:has-text("Entrar"), button:has-text("Join"), button:has-text("Ingressar")').first.click(timeout=5000)
        except Exception: pass
        time.sleep(15)
        try:
            page.locator('button:has-text("udio do computador"), button:has-text("Computer Audio"), button:has-text("Join Audio"), button:has-text("Ingressar por")').first.click(timeout=5000)
        except Exception: pass
        try:
            body = (page.evaluate('() => document.body.innerText') or '')[:400].replace('\n',' | ')
            print(f'[capture] pagina pos-join: {page.url[:90]} :: {body[:200]}')
        except Exception: pass
    else:
        page.goto(spec['webcast_url'], timeout=90000, wait_until='domcontentloaded')
        time.sleep(5)
        try_register(page)
    time.sleep(15)
    # ZOOM: depois de registrar, ENTRAR NA SALA (web client) — sem isso grava silencio da pagina de confirmacao
    try:
        import re as _re
        if 'zoom.us' in page.url:
            tk = None
            m = _re.search(r'[?&]tk=([^&#]+)', page.url)
            if m: tk = m.group(1)
            # procura link de join /w/ ou /wc/ na pagina de confirmacao
            join = page.evaluate('''() => { const a=[...document.querySelectorAll('a')].find(x=>/zoom.us\/(w|wc)\//.test(x.href)); return a?a.href:null }''')
            wid = None
            m2 = _re.search(r'/w/(\d+)', join or '')
            if m2: wid = m2.group(1)
            if not wid:
                body = page.evaluate('() => document.body.innerText') or ''
                m3 = _re.search(r'(\d{3})[ .-]?(\d{4})[ .-]?(\d{4})', body)
                if m3: wid = ''.join(m3.groups())
            if not wid and spec.get('zoom_webinar_id'): wid = str(spec['zoom_webinar_id']).replace(' ','')
            host = _re.match(r'https://[^/]+', page.url).group(0)
            alvo = join or (f"{host}/wc/{wid}/join" + (f"?tk={tk}" if tk else '') if wid else None)
            if alvo:
                print(f'[capture] entrando na sala: {alvo[:80]}...')
                page.goto(alvo, timeout=90000, wait_until='domcontentloaded')
                time.sleep(12)
                # web client: preencher nome/email se pedir e clicar em entrar
                try:
                    for sel, val in [('input[type=text]', os.environ.get('REG_NAME','Philippe Molina')),
                                     ('input[type=email]', os.environ.get('REG_EMAIL',''))]:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=2000): el.fill(val)
                except Exception: pass
                try:
                    page.locator('button:has-text("Entrar"), button:has-text("Join"), button:has-text("Ingressar")').first.click(timeout=4000)
                except Exception: pass
                time.sleep(15)
                # alguns clients pedem "ingressar por audio do computador"
                try:
                    page.locator('button:has-text("udio do computador"), button:has-text("Computer Audio"), button:has-text("Join Audio")').first.click(timeout=4000)
                except Exception: pass
            else:
                print('[capture] AVISO: nao achei link/ID para entrar na sala')
    except Exception as e:
        print(f'[capture] erro ao entrar na sala: {e}')
    time.sleep(10)
    if 'u' in stream_url:
        threading.Thread(target=record_hls, args=(stream_url['u'],), daemon=True).start()
        modo = 'hls'
    else:
        record_pulse()
        modo = 'pulse'
    # CONFIRMACAO DE CONEXAO auto-reportada (pedido do usuario 23/07):
    # commita marcador no repo assim que a gravacao comeca
    try:
        import subprocess as sp
        ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        os.makedirs('logs', exist_ok=True)
        rid = os.environ.get('GITHUB_RUN_ID', 'local')
        with open(f'logs/CONECTADO_{rid}.txt', 'w') as f:
            f.write(f"CONECTADO {ts}\nticker={spec.get('ticker')} evento={spec.get('quarter')}\nmodo={modo}\nurl_pagina={page.url[:120]}\n")
        sp.run(['git','config','user.name','earnings-bot']); sp.run(['git','config','user.email','bot@users.noreply.github.com'])
        for i in (1,2,3):
            sp.run(['git','pull','-q','--rebase'])
            sp.run(['git','add','logs/'])
            ok = sp.run(['git','commit','-q','-m',f'CONECTADO {spec.get("ticker")} {ts}']).returncode == 0
            if ok and sp.run(['git','push','-q']).returncode == 0: break
            time.sleep(i*7)
        print('[capture] confirmacao CONECTADO commitada')
    except Exception as e:
        print(f'[capture] erro ao commitar CONECTADO: {e}')
    # duração máxima de gravação: 3h; fim antecipado por silêncio é tratado no live_loop
    t_end = time.time() + 3*3600
    while time.time() < t_end and not os.path.exists('work/audio/END'):
        time.sleep(30)
    open('work/audio/END','w').close()
    browser.close()
print('captura encerrada')
