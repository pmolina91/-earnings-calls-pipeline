#!/usr/bin/env python3
"""Dry-run de transcrição: baixa áudio de um replay (yt-dlp), corta N min, transcreve e salva."""
import json, sys, os, subprocess, time
spec = json.load(open(sys.argv[1]))
os.makedirs('work', exist_ok=True)
t0=time.time()
subprocess.run(['yt-dlp','-q','-x','--audio-format','wav','--postprocessor-args','-ac 1 -ar 16000',
                '-o','work/replay.%(ext)s', spec['replay_url']], check=True)
print(f'download em {time.time()-t0:.0f}s')
lim = str(spec.get('limit_seconds', 900))
subprocess.run(['ffmpeg','-loglevel','error','-i','work/replay.wav','-t',lim,'-c','copy','work/cut.wav'], check=True)
from faster_whisper import WhisperModel
t0=time.time()
m = WhisperModel('models/faster-whisper-small', device='cpu', compute_type='int8')
segs, info = m.transcribe('work/cut.wav', language='pt', vad_filter=True, beam_size=5)
lines=[]
for s in segs:
    mm,ss = divmod(int(s.start),60)
    lines.append(f'[{mm:02d}:{ss:02d}] {s.text.strip()}')
os.makedirs('transcripts', exist_ok=True)
out = f"transcripts/TESTE_{spec['label']}.md"
open(out,'w').write(f"# TESTE de transcrição — {spec['label']}\n\n" + '\n'.join(lines) + '\n')
print(f'transcrito em {(time.time()-t0)/60:.1f}min | {len(lines)} segmentos | {out}')
