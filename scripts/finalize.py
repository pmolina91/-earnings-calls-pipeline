#!/usr/bin/env python3
"""Concatena o audio, retranscreve com qualidade (beam 5) e publica a versao FINAL:
- corrige termos + limpa artefatos
- separa a fala por interlocutor (operador/analista/executivo), SEM timestamps
- APAGA a transcricao ao vivo do Notion e publica a final legivel
Um raw com timestamps fica so' no repo (transcripts/raw/) para conferencia/alinhamento.
"""
import json, sys, os, glob, subprocess
from faster_whisper import WhisperModel
import notion_api
import format_transcript

spec = json.load(open(sys.argv[1]))
chunks = sorted(glob.glob('work/audio/chunk_*.wav'))
if not chunks: print('sem audio'); sys.exit(0)
with open('work/list.txt','w') as f:
    for c in chunks: f.write(f"file '{os.path.abspath(c)}'\n")
subprocess.run(['ffmpeg','-loglevel','error','-f','concat','-safe','0','-i','work/list.txt',
                '-c','copy','work/full.wav'], check=True)
m = WhisperModel('models/faster-whisper-small', device='cpu', compute_type='int8')
_lang = spec.get('language','pt') or None
if _lang == 'auto': _lang = None
segs,_ = m.transcribe('work/full.wav', language=_lang, vad_filter=True, beam_size=5,
                      hotwords=(spec.get('hotwords','') or None))
seg_list = list(segs)

# raw com timestamps (so' repo, para conferencia) ---------------------------------
raw_lines = []
for s in seg_list:
    mm,ss = divmod(int(s.start),60); hh,mm = divmod(mm,60)
    raw_lines.append(f'[{hh:02d}:{mm:02d}:{ss:02d}] {s.text.strip()}')
os.makedirs('transcripts/raw', exist_ok=True)
open(f"transcripts/raw/{spec['ticker_short']}_{spec['quarter']}_raw.txt",'w').write('\n'.join(raw_lines)+'\n')

# transcricao FINAL legivel: corrigida, sem timestamps, por interlocutor -----------
seg_texts = [s.text for s in seg_list]
glossario = spec.get('glossario')  # opcional: {'padrao_regex':'substituicao'} por empresa
final_md = format_transcript.to_speaker_text(seg_texts, lang=(spec.get('language','pt') or 'pt'), glossario=glossario)

out=f"transcripts/{spec['ticker_short']}_{spec['quarter']}.md"
os.makedirs('transcripts',exist_ok=True)
open(out,'w').write(f"# {spec['ticker_short']} — Call {spec['quarter']} (transcricao final, por interlocutor)\n\n{final_md}\n")

if os.path.exists('work/notion_page_id') and os.environ.get('NOTION_TOKEN'):
    page_id=open('work/notion_page_id').read().strip()
    # 1) apaga a transcricao AO VIVO (preserva secoes do cerebro se ja existirem)
    n = notion_api.delete_live_blocks(page_id)
    print(f'[final] {n} blocos da transcricao ao vivo apagados')
    # 2) publica a transcricao final legivel, por interlocutor, sem timestamps
    notion_api.append_markdown(page_id, final_md[:900000],
                               heading='Transcrição final (por interlocutor)')
    # 3) tira a marcacao [LIVE] do titulo
    import requests
    requests.patch(f'https://api.notion.com/v1/pages/{page_id}',
        headers={'Authorization':f"Bearer {os.environ['NOTION_TOKEN']}",'Notion-Version':'2022-06-28','Content-Type':'application/json'},
        json={'properties':{'Name':{'title':[{'text':{'content':f"Call {spec['quarter']} - {spec['ticker_short']}"}}]}}})
else:
    print('[final] Notion desativado — transcricao so no repo')
print('final publicada:', out)
