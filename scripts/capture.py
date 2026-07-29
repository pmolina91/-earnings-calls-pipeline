#!/usr/bin/env python3
"""Espera até T-10min, abre o webcast, registra com a identidade (secrets) e grava o áudio
em chunks de 2min em work/audio/. Estratégia dupla:
 A) sniffing de rede: se o player expõe stream HLS/DASH (m3u8/mpd/mp3/aac), grava via ffmpeg direto.
 B) fallback: áudio da aba via PulseAudio virtual sink + ffmpeg (funciona p/ Zoom web client etc).
Sentinela work/audio/END criada ao detectar fim (silêncio prolongado pós-início ou stream fechado)."""
import json, sys, os, time, re, subprocess, threading, glob
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

spec = json.load(open(sys.argv[1]))
os.makedirs('work/audio', exist_ok=True)
call = datetime.fromisoformat(spec['call_datetime_utc'].replace('Z','+00:00'))
# join_offset_seconds: quando ENTRAR na sala, relativo ao horario do call.
#  -600 (default) = T-10min (runner "cedo"); +120 = T+2min (runner "ao vivo", ja entra live e
#  nunca cai na sala de espera). Permite dois runners escalonados (ver docs/PROCESSO-captura.md).
offset = float(spec.get('join_offset_seconds', -600))
wait = (call - datetime.now(timezone.utc)).total_seconds() + offset
if wait > 0:
    print(f'esperando {wait/60:.0f}min ate o horario de entrada (offset={offset}s)...'); time.sleep(wait)

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
        '-f','segment','-segment_time', str(spec.get('chunk_seconds', 45)),'-reset_timestamps','1',
        'work/audio/chunk_%04d.wav'])

_ff = {'p': None, 'idx': 0}
def record_pulse():
    print('gravando via PulseAudio (áudio da aba)')
    subprocess.run(['pactl','set-default-sink','cap'], check=False)  # re-arma roteamento antes de gravar
    # -segment_start_number preserva a numeracao ao reiniciar (nao sobrescreve chunks ja gravados)
    _ff['p'] = subprocess.Popen(['ffmpeg','-loglevel','warning','-f','pulse','-i','cap.monitor','-ac','1','-ar','16000',
        '-f','segment','-segment_time', str(spec.get('chunk_seconds', 45)),'-reset_timestamps','1',
        '-segment_start_number', str(_ff['idx']),'work/audio/chunk_%04d.wav'])

# PulseAudio ANTES do navegador (senao o Chromium nasce sem sink correto)
subprocess.run(['pulseaudio','--start','--exit-idle-time=-1'], check=False)
subprocess.run(['pactl','load-module','module-null-sink','sink_name=cap','sink_properties=device.description=cap'], check=False)
subprocess.run(['pactl','set-default-sink','cap'], check=False)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False,
        ignore_default_args=['--mute-audio'],
        args=['--autoplay-policy=no-user-gesture-required', '--no-sandbox', '--disable-dev-shm-usage'])
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
            for sel, val in [('#input-for-name', os.environ.get('REG_NAME','Philippe Molina')),
                             ('input[type=text]', os.environ.get('REG_NAME','Philippe Molina')),
                             ('#input-for-email', os.environ.get('REG_EMAIL','')),
                             ('input[type=email]', os.environ.get('REG_EMAIL',''))]:
                el = page.locator(sel).first
                if el.is_visible(timeout=2500): el.fill(val)
        except Exception: pass
        for _tent in range(3):
            try:
                page.locator('button:has-text("Entrar"), button:has-text("Join"), button:has-text("Ingressar")').first.click(timeout=5000)
                time.sleep(10)
            except Exception:
                break
        time.sleep(10)
        try:
            body = (page.evaluate('() => document.body.innerText') or '')[:300].replace('\n',' | ')
            print(f'[capture] estado sala: {page.url[:90]} :: {body[:200]}')
        except Exception: pass
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
    # players de webcast/radio exigem clique no play (Zoom nao); tentar generico
    try:
        for s in ['button[aria-label*=play i]', 'button[title*=play i]', '.play', '.vjs-big-play-button', 'button:has-text("Play")', 'button:has-text("Ouvir")']:
            try:
                el = page.locator(s).first
                if el.is_visible(timeout=1500): el.click(); print(f'[capture] play clicado: {s}'); break
            except Exception: pass
        page.evaluate('() => { for (const m of document.querySelectorAll("audio,video")) { try { m.muted=false; m.play(); } catch(e){} } }')
    except Exception as e:
        print(f'[capture] play generico: {e}')
    forca_pulse = 'zoom.us' in (spec.get('join_url','') + spec.get('webcast_url','')) or spec.get('force_pulse')
    if 'u' in stream_url and not forca_pulse:
        threading.Thread(target=record_hls, args=(stream_url['u'],), daemon=True).start()
        modo = 'hls'
    else:
        record_pulse()
        modo = 'pulse'  # Zoom web client = WebRTC; sniff pega asset errado (mp3 de notificacao) — sempre pulse
    # VERIFICACAO DE SALA: so declara conectado se a pagina parecer a sala do webinar
    em_sala = False
    try:
        _body = (page.evaluate('() => document.body.innerText') or '').lower()
        em_sala = (('registration' not in page.url and 'register' not in page.url) and
                   ('/wc/' in page.url or any(s in _body for s in ['aguardando','aguarde','wait for','waiting for','has not started','não começou','nao comecou','leave','sair','audio','áudio','webinar em andamento','host to start','organizador'])))
    except Exception:
        pass
    # CONFIRMACAO DE CONEXAO auto-reportada (pedido do usuario 23/07):
    # commita marcador no repo assim que a gravacao comeca
    try:
        import subprocess as sp
        ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        os.makedirs('logs', exist_ok=True)
        rid = os.environ.get('GITHUB_RUN_ID', 'local')
        marcador = 'CONECTADO' if em_sala else 'FALHA_CONEXAO'
        with open(f'logs/{marcador}_{rid}.txt', 'w') as f:
            f.write(f"{marcador} {ts}\nticker={spec.get('ticker')} evento={spec.get('quarter')}\nmodo={modo}\nem_sala={em_sala}\nurl_pagina={page.url[:120]}\n")
        sp.run(['git','config','user.name','earnings-bot']); sp.run(['git','config','user.email','bot@users.noreply.github.com'])
        for i in (1,2,3):
            sp.run(['git','pull','-q','--rebase'])
            sp.run(['git','add','logs/'])
            ok = sp.run(['git','commit','-q','-m',f'{marcador} {spec.get("ticker")} {ts}']).returncode == 0
            if ok and sp.run(['git','push','-q']).returncode == 0: break
            time.sleep(i*7)
        print('[capture] confirmacao CONECTADO commitada')
        # watchdog de audio (SOM_OK/ALERTA_SILENCIO em ~1 min; re-alerta a cada 5 min)
        import subprocess as sp2
        sp2.Popen(['python3','scripts/audio_watchdog.py', modo, str(spec.get('ticker')), spec.get('call_datetime_utc','')])
    except Exception as e:
        print(f'[capture] erro ao commitar CONECTADO: {e}')
    # duração máxima de gravação. NUNCA encerra por silêncio — só no t_end ou sinal END externo.
    # A cada ciclo: re-arma o áudio (sobrevive à transição sala-de-espera→ao vivo) e reinicia o
    # ffmpeg se ele travar (sem chunk novo). Isso ataca a causa da perda do começo dos calls.
    t_end = time.time() + float(spec.get('max_capture_minutes', 180))*60
    last_n, last_grow = -1, time.time()
    while time.time() < t_end and not os.path.exists('work/audio/END'):
        time.sleep(20)
        try:
            subprocess.run(['pactl','set-default-sink','cap'], check=False)  # mantém roteamento do áudio
            # re-clica "entrar por áudio do computador" / play e desmuta (main thread = seguro p/ Playwright)
            try:
                page.locator('button:has-text("udio do computador"), button:has-text("Computer Audio"), button:has-text("Join Audio")').first.click(timeout=1500)
            except Exception: pass
            try:
                page.evaluate('() => { for (const m of document.querySelectorAll("audio,video")) { try{m.muted=false;m.play();}catch(e){} } }')
            except Exception: pass
            # detecta ffmpeg travado (sem chunk novo por ~100s) e reinicia sem perder a numeração
            n = len(glob.glob('work/audio/chunk_*.wav'))
            if n > last_n:
                last_n, last_grow = n, time.time()
            elif modo == 'pulse' and time.time() - last_grow > 100:
                print('[capture] ffmpeg sem chunk novo — reiniciando gravação')
                _ff['idx'] = n
                try:
                    if _ff['p']: _ff['p'].kill()
                except Exception: pass
                record_pulse(); last_grow = time.time()
        except Exception as e:
            print(f'[capture] manutenção: {e}')
    open('work/audio/END','w').close()
    try: browser.close()
    except Exception: pass
print('captura encerrada')
