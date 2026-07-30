#!/usr/bin/env python3
"""Inspeciona + TESTA registro/play de um webcast (feedback real do fluxo de captura).
Faz: goto -> dump pre -> try_register (identidade dos secrets) -> play -> dump pos (media tocando?).
Uso: python3 scripts/inspect_webcast.py <webcast_url>"""
import json, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
from registration import try_register

url = sys.argv[1]
NAME = os.environ.get('REG_NAME', 'Test User')
EMAIL = os.environ.get('REG_EMAIL', 'test@example.com')
COMPANY = os.environ.get('REG_COMPANY', 'Test Co')
PHONE = os.environ.get('REG_PHONE', '')
out = {'url': url}

def media(p):
    try:
        return p.evaluate('()=>[...document.querySelectorAll("audio,video")].map(m=>({src:(m.currentSrc||m.src||"").slice(0,120),paused:m.paused,muted:m.muted,ready:m.readyState,dur:m.duration}))')
    except Exception as e:
        return {'err': str(e)[:80]}

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, ignore_default_args=['--mute-audio'],
        args=['--autoplay-policy=no-user-gesture-required', '--no-sandbox', '--disable-dev-shm-usage'])
    ctx = b.new_context(locale='pt-BR'); p = ctx.new_page()
    reqs = []
    p.on('request', lambda r: reqs.append(r.url) if any(x in r.url.lower() for x in ['.m3u8','.mp3','.aac','.mpd','stream','/media','/audio','edge','rtmp']) else None)
    p.goto(url, timeout=90000, wait_until='domcontentloaded'); time.sleep(6)
    out['pre_title'] = p.title()
    out['pre_inputs'] = p.evaluate('()=>[...document.querySelectorAll("input")].map(i=>({type:i.type,name:i.name}))')
    out['pre_buttons'] = p.evaluate('()=>[...document.querySelectorAll("button,[role=button],input[type=submit]")].map(b=>((b.innerText||b.value||b.getAttribute("aria-label")||"")).trim()).filter(Boolean).slice(0,20)')
    # REGISTRO
    try:
        out['register_log'] = try_register(p, NAME, EMAIL, COMPANY, PHONE, 'Buy side')
    except Exception as e:
        out['register_log'] = ['EXC:' + str(e)[:100]]
    time.sleep(8)
    out['post_title'] = p.title(); out['post_url'] = p.url[:120]
    out['post_media'] = media(p)
    # tenta play generico + m.play em todos frames
    for s in ['button[aria-label*=play i]','button[title*=play i]','.play','.vjs-big-play-button','button:has-text("Play")','button:has-text("Listen")']:
        try:
            el = p.locator(s).first
            if el.is_visible(timeout=1000): el.click(); out.setdefault('played_click', s); break
        except Exception: pass
    for fr in p.frames:
        try: fr.evaluate('()=>{for(const m of document.querySelectorAll("audio,video")){try{m.muted=false;m.play()}catch(e){}}}')
        except Exception: pass
    time.sleep(6)
    out['after_play_media'] = media(p)
    out['post_buttons'] = p.evaluate('()=>[...document.querySelectorAll("button,[role=button]")].map(b=>((b.innerText||b.getAttribute("aria-label")||"")).trim()).filter(Boolean).slice(0,20)')
    out['post_body'] = (p.evaluate('()=>document.body.innerText') or '')[:500]
    out['media_requests'] = list(dict.fromkeys(reqs))[:25]
    try: b.close()
    except Exception: pass
print(json.dumps(out, indent=1, ensure_ascii=False))
