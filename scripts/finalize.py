#!/usr/bin/env python3
"""Concatena o áudio, retranscreve com qualidade (beam 5) e publica a versão final."""
import json, sys, os, glob, subprocess
from faster_whisper import WhisperModel
import notion_api

spec = json.load(open(sys.argv[1]))
chunks = sorted(glob.glob('work/audio/chunk_*.wav'))
if not chunks: print('sem áudio'); sys.exit(0)
with open('work/list.txt','w') as f:
    for c in chunks: f.write(f"file '{os.path.abspath(c)}'\n")
subprocess.run(['ffmpeg','-loglevel','error','-f','concat','-safe','0','-i','work/list.txt',
                '-c','copy','work/full.wav'], check=True)
m = WhisperModel('models/faster-whisper-small', device='cpu', compute_type='int8')
segs,_ = m.transcribe('work/full.wav', language='pt', vad_filter=True, beam_size=5, hotwords=(spec.get('hotwords','') or None))
lines=[]
for s in segs:
    mm,ss = divmod(int(s.start),60); hh,mm = divmod(mm,60)
    lines.append(f'[{hh:02d}:{mm:02d}:{ss:02d}] {s.text.strip()}')
final='\n'.join(lines)
out=f"transcripts/{spec['ticker_short']}_{spec['quarter']}.md"
os.makedirs('transcripts',exist_ok=True)
open(out,'w').write(f"# {spec['ticker_short']} — Call {spec['quarter']}\n\n{final}\n")
import os as _os
if _os.path.exists('work/notion_page_id') and _os.environ.get('NOTION_TOKEN'):
    page_id=open('work/notion_page_id').read().strip()
    notion_api.append_text(page_id, final[:180000], heading='Transcrição final (consolidada, com timestamps)')
    import requests
    requests.patch(f'https://api.notion.com/v1/pages/{page_id}',
        headers={'Authorization':f"Bearer {_os.environ['NOTION_TOKEN']}",'Notion-Version':'2022-06-28','Content-Type':'application/json'},
        json={'properties':{'Name':{'title':[{'text':{'content':f"Call {spec['quarter']} - {spec['ticker_short']}"}}]}}})
else:
    print('[final] Notion desativado — transcrição só no repo')
print('final publicada:', out)
