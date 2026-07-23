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
    page.goto(spec['webcast_url'], timeout=90000, wait_until='domcontentloaded')
    time.sleep(5)
    try_register(page)
    time.sleep(20)  # dar tempo do player iniciar
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
