#!/usr/bin/env python3
"""Transcreve chunks conforme chegam e publica incrementalmente no Notion."""
import json, sys, os, time, glob
from faster_whisper import WhisperModel
import notion_api

spec = json.load(open(sys.argv[1]))
NOTION_ON = bool(os.environ.get('NOTION_TOKEN')) and spec.get('notion_database_id','').lower() not in ('', 'sera_preenchido', 'none', 'skip')
if not NOTION_ON:
    print('[live] NOTION desativado (sem token ou database) — transcrevendo sem publicar')
page_id_file = 'work/notion_page_id'
model = WhisperModel('models/faster-whisper-small', device='cpu', compute_type='int8')
print('[live] modelo ok')

# cria a página do call no Notion (com marcação LIVE)
page_id = None
if NOTION_ON:
    title = f"Call {spec['quarter']} - {spec['ticker_short']} [LIVE - transcrição automática em andamento]"
    page_id = notion_api.create_call_page(spec['notion_database_id'], title,
                                          spec['quarter'], spec['call_datetime_utc'][:10])
    open(page_id_file,'w').write(page_id)
    notion_api.append_text(page_id, f"Transcrição ao vivo iniciada. Fonte: {spec['webcast_url']}",
                           heading='Transcrição (ao vivo)')

done, empty_streak = set(), 0
HOT = spec.get('hotwords','') or None
LANG = spec.get('language','pt') or None
if LANG == 'auto': LANG = None  # deixa o whisper detectar
ultimo_texto = ''
while True:
    chunks = sorted(glob.glob('work/audio/chunk_*.wav'))
    new = [c for c in chunks if c not in done and os.path.getsize(c) > 60000
           and time.time()-os.path.getmtime(c) > 5]
    for c in new:
        try:
            segs,_ = model.transcribe(c, language=LANG, vad_filter=True, beam_size=5,
                                      hotwords=HOT, initial_prompt=(ultimo_texto[-200:] or None))
            text = ' '.join(s.text.strip() for s in segs).strip()
            if text: ultimo_texto = text
            if text:
                if NOTION_ON: notion_api.append_text(page_id, text)
                empty_streak = 0
            else:
                empty_streak += 1
            with open('work/transcript_live.txt','a') as f: f.write(text+'\n')
            print(f'[live] {os.path.basename(c)}: {len(text)} chars')
        except Exception as e:
            print(f'[live][ERRO] {c}: {e}')
        done.add(c)
    # fim: 5 chunks vazios seguidos (10min de silêncio) após já ter havido fala
    if empty_streak >= 5 and any(done):
        open('work/audio/END','w').close()
    if os.path.exists('work/audio/END') and not new:
        break
    time.sleep(10)
print('[live] encerrado')
