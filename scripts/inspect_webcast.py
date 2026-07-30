#!/usr/bin/env python3
"""Inspeciona a estrutura de uma pagina de webcast p/ diagnosticar captura de audio.
Dump JSON: media elements (top e iframes), iframes (origem), forms/inputs, botoes, requests de midia.
Uso: python3 scripts/inspect_webcast.py <webcast_url>"""
import json, sys, time
from playwright.sync_api import sync_playwright

url = sys.argv[1]
out = {'url': url}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, ignore_default_args=['--mute-audio'],
        args=['--autoplay-policy=no-user-gesture-required', '--no-sandbox', '--disable-dev-shm-usage'])
    ctx = b.new_context(); p = ctx.new_page()
    reqs = []
    p.on('request', lambda r: reqs.append(r.url) if any(x in r.url.lower() for x in ['.m3u8','.mp3','.aac','.mpd','stream','/media','audio']) else None)
    try:
        p.goto(url, timeout=90000, wait_until='domcontentloaded')
    except Exception as e:
        out['goto_err'] = str(e)[:120]
    time.sleep(12)
    out['title'] = p.title(); out['final_url'] = p.url
    def ev(expr, default=None):
        try: return p.evaluate(expr)
        except Exception as e: return {'err': str(e)[:80]}
    out['top_media'] = ev('()=>[...document.querySelectorAll("audio,video")].map(m=>({tag:m.tagName,src:(m.currentSrc||m.src||"").slice(0,120),paused:m.paused,muted:m.muted}))')
    out['iframes'] = ev('()=>[...document.querySelectorAll("iframe")].map(f=>({src:(f.src||"").slice(0,140)}))')
    out['forms'] = ev('()=>document.querySelectorAll("form").length')
    out['inputs'] = ev('()=>[...document.querySelectorAll("input")].map(i=>({type:i.type,name:(i.name||"").slice(0,40),ph:(i.placeholder||"").slice(0,40)}))')
    out['buttons'] = ev('()=>[...document.querySelectorAll("button,[role=button],a")].map(b=>((b.innerText||b.getAttribute("aria-label")||"")).trim()).filter(Boolean).slice(0,30)')
    out['body'] = (ev('()=>document.body.innerText') or '')[:900] if isinstance(ev('()=>1'),(int,dict)) else ''
    try: out['body'] = (p.evaluate('()=>document.body.innerText') or '')[:900]
    except Exception: pass
    # tenta dar play em TODOS os frames (inclusive iframes same-origin) e ver se destrava
    for fr in p.frames:
        try: fr.evaluate('()=>{for(const m of document.querySelectorAll("audio,video,button")){try{if(m.play)m.play();if(/play|listen|ouvir/i.test(m.innerText||m.getAttribute&&m.getAttribute("aria-label")||""))m.click&&m.click();m.muted=false;}catch(e){}}}')
        except Exception: pass
    time.sleep(4)
    out['frames'] = []
    for fr in p.frames:
        info = {'url': (fr.url or '')[:90]}
        try:
            info['media'] = fr.evaluate('()=>[...document.querySelectorAll("audio,video")].map(m=>({src:(m.currentSrc||m.src||"").slice(0,120),paused:m.paused,muted:m.muted}))')
        except Exception as e:
            info['media_err'] = str(e)[:70]  # cross-origin => SecurityError aqui
        out['frames'].append(info)
    out['media_requests'] = list(dict.fromkeys(reqs))[:25]
    try: b.close()
    except Exception: pass
print(json.dumps(out, indent=1, ensure_ascii=False))
