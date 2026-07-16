#!/usr/bin/env python3
"""Dry-run de transcrição: baixa áudio de um replay, corta N min, transcreve e salva.
Fontes suportadas: YouTube (yt-dlp) ou URL direta de áudio/stream (ffmpeg).
Em erro, grava traceback em work/error.txt para diagnóstico via repo."""
import json, sys, os, subprocess, time, traceback

def main():
    spec = json.load(open(sys.argv[1]))
    os.makedirs('work', exist_ok=True)
    t0=time.time()
    url = spec.get('replay_url','')
    direct = spec.get('direct_audio_url','')
    if direct:
        subprocess.run(['ffmpeg','-loglevel','error','-i',direct,'-ac','1','-ar','16000',
                        '-t',str(spec.get('limit_seconds',900)),'work/cut.wav'], check=True)
    else:
        r = subprocess.run(['yt-dlp','-x','--audio-format','wav','--postprocessor-args','-ac 1 -ar 16000',
                        '-o','work/replay.%(ext)s', url], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f'yt-dlp falhou:\nSTDOUT:{r.stdout[-2000:]}\nSTDERR:{r.stderr[-3000:]}')
        subprocess.run(['ffmpeg','-loglevel','error','-i','work/replay.wav','-t',str(spec.get('limit_seconds',900)),'-c','copy','work/cut.wav'], check=True)
    print(f'audio pronto em {time.time()-t0:.0f}s')
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

if __name__ == '__main__':
    try:
        main()
    except Exception:
        os.makedirs('work', exist_ok=True)
        open('work/error.txt','w').write(traceback.format_exc())
        print(traceback.format_exc())
        sys.exit(1)
