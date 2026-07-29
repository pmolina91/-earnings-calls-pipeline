#!/usr/bin/env python3
"""Backfill pelo AUDIO OFICIAL do RI (Camada 5 — espinha dorsal da completude).
Baixa o audio/replay oficial do call INTEIRO (inclui a abertura que a captura ao vivo perde),
transcreve, formata por interlocutor (sem timestamps) e SUBSTITUI a transcricao ao vivo na nota
do Notion — garantindo a nota completa independentemente de falhas da captura ao vivo.

Fontes de audio (no spec, em ordem de preferencia): direct_audio_url | rss_url | replay_url (yt-dlp).
Requer NOTION_TOKEN no ambiente. Uso: python3 scripts/check_official_replay.py staging/SANB11_2T26.json
Se o audio oficial ainda nao estiver disponivel, sai com codigo 3 (re-tentar mais tarde)."""
import json, sys, os, subprocess, glob, urllib.request, re, gzip
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notion_api, format_transcript

spec = json.load(open(sys.argv[1]))
os.makedirs('work', exist_ok=True)

def baixar_audio():
    direct = spec.get('direct_audio_url'); rss = spec.get('rss_url'); replay = spec.get('replay_url')
    if rss and not direct:
        req = urllib.request.Request(rss, headers={'User-Agent':'Mozilla/5.0','Accept-Encoding':'gzip'})
        raw = urllib.request.urlopen(req, timeout=60).read()
        try: raw = gzip.decompress(raw)
        except Exception: pass
        m = re.search(r'<enclosure[^>]*url="([^"]+)"', raw.decode('utf-8','ignore'))
        if m: direct = m.group(1).replace('&amp;','&')
    if direct:
        r = subprocess.run(['ffmpeg','-y','-loglevel','error','-i',direct,'-ac','1','-ar','16000','work/oficial.wav'])
        return r.returncode == 0
    if replay:
        r = subprocess.run(['yt-dlp','-x','--audio-format','wav','--postprocessor-args','-ac 1 -ar 16000',
                            '-o','work/oficial.%(ext)s', replay])
        if r.returncode == 0 and os.path.exists('work/oficial.wav'): return True
    return False

if not baixar_audio():
    print('[replay] audio oficial ainda indisponivel — re-tentar mais tarde'); sys.exit(3)

from faster_whisper import WhisperModel
m = WhisperModel('models/faster-whisper-small', device='cpu', compute_type='int8')
lang = (spec.get('language','pt') or None)
if lang == 'auto': lang = None
segs,_ = m.transcribe('work/oficial.wav', language=lang, vad_filter=True, beam_size=5,
                      hotwords=(spec.get('hotwords','') or None))
seg_texts = [s.text for s in segs]
final_md = format_transcript.to_speaker_text(seg_texts, lang=(spec.get('language','pt') or 'pt'),
                                             glossario=spec.get('glossario'))
out = f"transcripts/{spec['ticker_short']}_{spec['quarter']}_OFICIAL.md"
os.makedirs('transcripts', exist_ok=True); open(out,'w').write(final_md + '\n')
print('[replay] transcricao oficial (completa) salva:', out, '-', len(final_md), 'chars')

if os.environ.get('NOTION_TOKEN'):
    pid = notion_api.find_call_page(spec['notion_database_id'], f"Call {spec['quarter']} - {spec['ticker_short']}")
    if pid:
        n = notion_api.delete_live_blocks(pid)
        notion_api.append_markdown(pid, final_md[:900000],
                                   heading='Transcrição final (áudio oficial do RI — call completo)')
        print(f'[replay] Notion: {n} blocos ao vivo apagados; transcricao oficial completa publicada em {pid}')
    else:
        print('[replay] nao achei a pagina do call no Notion; transcricao ficou so no repo')
