#!/usr/bin/env python3
"""Transcreve chunks conforme chegam e publica incrementalmente no Notion."""
import json, sys, os, time, glob
from faster_whisper import WhisperModel
import notion_api

spec = json.load(open(sys.argv[1]))
page_id_file = 'work/notion_page_id'
model = WhisperModel('models/faster-whisper-small', device='cpu', compute_type='int8')
print('[live] modelo ok')

# cria a página do call no Notion (com marcação LIVE)
title = f"Call {spec['quarter']} - {spec['ticker_short']} [LIVE - transcrição automática em andamento]"
page_id = notion_api.create_call_page(spec['notion_database_id'], title,
                                      spec['quarter'], spec['call_datetime_utc'][:10])
open(page_id_file,'w').write(page_id)
notion_api.append_text(page_id, f"Transcrição ao vivo iniciada. Fonte: {spec['webcast_url']}",
                       heading='Transcrição (ao vivo)')

done, empty_streak = set(), 0
while True:
    chunks = sorted(glob.glob('work/audio/chunk_*.wav'))
    new = [c for c in chunks if c not in done and os.path.getsize(c) > 60000
           and time.time()-os.path.getmtime(c) > 5]
    for c in new:
        try:
            segs,_ = model.transcribe(c, language='pt', vad_filter=True, beam_size=2)
            text = ' '.join(s.text.strip() for s in segs).strip()
            if text:
                notion_api.append_text(page_id, text); empty_streak = 0
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
