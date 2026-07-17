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
    rss = spec.get('rss_url','')
    if rss and not direct:
        import urllib.request, re, gzip, io
        req = urllib.request.Request(rss, headers={'User-Agent':'Mozilla/5.0','Accept-Encoding':'gzip'})
        raw = urllib.request.urlopen(req, timeout=60).read()
        try: raw = gzip.decompress(raw)
        except Exception: pass
        xml = raw.decode('utf-8', 'ignore')
        m2 = re.search(r'<enclosure[^>]*url="([^"]+)"', xml)
        if not m2: raise RuntimeError('nenhum enclosure no RSS')
        direct = m2.group(1).replace('&amp;','&')
        print('mp3 do RSS:', direct[:120])
    if direct:
        cmd = ['ffmpeg','-loglevel','error','-i',direct,'-ac','1','-ar','16000']
        lim = spec.get('limit_seconds')
        if lim: cmd += ['-t', str(lim)]
        subprocess.run(cmd + ['work/cut.wav'], check=True)
    else:
        r = subprocess.run(['yt-dlp','-x','--audio-format','wav','--postprocessor-args','-ac 1 -ar 16000',
                        '-o','work/replay.%(ext)s', url], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f'yt-dlp falhou:\nSTDOUT:{r.stdout[-2000:]}\nSTDERR:{r.stderr[-3000:]}')
        cmd = ['ffmpeg','-loglevel','error','-i','work/replay.wav']
        lim = spec.get('limit_seconds')
        if lim: cmd += ['-t', str(lim)]
        subprocess.run(cmd + ['-c','copy','work/cut.wav'], check=True)
    print(f'audio pronto em {time.time()-t0:.0f}s')
    os.makedirs('transcripts', exist_ok=True)
    from faster_whisper import WhisperModel
    t0=time.time()
    m = WhisperModel('models/faster-whisper-small', device='cpu', compute_type='int8')
    if spec.get('live_style'):
        # simular o AO VIVO: chunks de 60s, beam 2 (mesma config do live_loop)
        os.makedirs('work/chunks', exist_ok=True)
        subprocess.run(['ffmpeg','-loglevel','error','-i','work/cut.wav','-f','segment',
                        '-segment_time','60','-reset_timestamps','1','work/chunks/c_%04d.wav'], check=True)
        import glob
        chunks = sorted(glob.glob('work/chunks/c_*.wav'))
        textos = []
        for i, ck in enumerate(chunks):
            segs, _ = m.transcribe(ck, language='pt', vad_filter=True, beam_size=2)
            textos.append(' '.join(s.text.strip() for s in segs).strip())
            if i % 10 == 0: print(f'chunk {i}/{len(chunks)} em {time.time()-t0:.0f}s', flush=True)
        out = f"transcripts/LIVE_{spec['label']}.txt"
        open(out,'w').write('\n\n'.join(textos) + '\n')
        print(f'live-style: {len(chunks)} chunks em {(time.time()-t0)/60:.1f}min | {out}')
    else:
        segs, info = m.transcribe('work/cut.wav', language='pt', vad_filter=True, beam_size=5)
        lines=[]
        for s in segs:
            mm,ss = divmod(int(s.start),60)
            lines.append(f'[{mm:02d}:{ss:02d}] {s.text.strip()}')
        out = f"transcripts/TESTE_{spec['label']}.md"
        open(out,'w').write(f"# TESTE de transcrição — {spec['label']}\n\n" + '\n'.join(lines) + '\n')
        print(f'transcrito em {(time.time()-t0)/60:.1f}min | {len(lines)} segmentos | {out}')
    # transcrição oficial (PDF) para comparação
    if spec.get('official_pdf_url'):
        import urllib.request
        urllib.request.urlretrieve(spec['official_pdf_url'], 'work/oficial.pdf')
        from pypdf import PdfReader
        txt = '\n'.join((p.extract_text() or '') for p in PdfReader('work/oficial.pdf').pages)
        open(f"transcripts/OFICIAL_{spec['label']}.txt",'w').write(txt)
        print(f'transcricao oficial: {len(txt)} chars')

if __name__ == '__main__':
    try:
        main()
    except Exception:
        os.makedirs('work', exist_ok=True)
        open('work/error.txt','w').write(traceback.format_exc())
        print(traceback.format_exc())
        sys.exit(1)
