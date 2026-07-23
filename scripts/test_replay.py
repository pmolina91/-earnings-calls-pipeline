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
        # AO VIVO v2: chunks de 120s, beam 5, hotwords (glossário) e contexto encadeado
        os.makedirs('work/chunks', exist_ok=True)
        seg = str(spec.get('chunk_seconds', 120))
        subprocess.run(['ffmpeg','-loglevel','error','-i','work/cut.wav','-f','segment',
                        '-segment_time',seg,'-reset_timestamps','1','work/chunks/c_%04d.wav'], check=True)
        import glob
        chunks = sorted(glob.glob('work/chunks/c_*.wav'))
        textos = []
        hot = spec.get('hotwords','') or None
        lang = spec.get('language','pt') or None
        if lang == 'auto': lang = None
        # publicacao incremental no Notion (ensaio do fluxo do live_loop)
        notion_page = None
        db = spec.get('notion_database_id','')
        if os.environ.get('NOTION_TOKEN') and db:
            import notion_api
            titulo = spec.get('notion_title') or f"ENSAIO LIVE {spec['label']}"
            chave = f"Call {spec.get('quarter','')} - " if spec.get('quarter') else titulo
            notion_page = notion_api.find_call_page(db, chave) if spec.get('quarter') else None
            if notion_page:
                notion_api.append_text(notion_page, 'Transcrição do replay (nova sessão).', heading='───────────')
            else:
                notion_page = notion_api.create_call_page(db, titulo,
                    spec.get('quarter','TESTE'), time.strftime('%Y-%m-%d'))
            notion_api.append_text(notion_page, 'Ensaio de transcrição ao vivo (replay). Pode apagar.',
                                   heading='Transcrição (ao vivo)')
            print('notion page criada:', notion_page, flush=True)
        for i, ck in enumerate(chunks):
            prev = textos[-1][-200:] if textos else None
            segs, _ = m.transcribe(ck, language=lang, vad_filter=True, beam_size=5,
                                   hotwords=hot, initial_prompt=prev)
            txt = ' '.join(s.text.strip() for s in segs).strip()
            textos.append(txt)
            if notion_page and txt:
                try:
                    import notion_api
                    notion_api.append_text(notion_page, txt)
                except Exception as e:
                    print(f'[notion][ERRO] chunk {i}: {e}', flush=True)
            if i % 5 == 0: print(f'chunk {i}/{len(chunks)} em {time.time()-t0:.0f}s', flush=True)
        if notion_page:
            try:
                import notion_api, requests as _rq
                _rq.patch(f'https://api.notion.com/v1/pages/{notion_page}', headers=notion_api.H(),
                    json={'properties': {'Name': {'title':[{'text':{'content': f"ENSAIO LIVE {spec['label']} [CONCLUÍDO]"}}]}}})
            except Exception as e:
                print(f'[notion][ERRO] titulo final: {e}', flush=True)
        out = f"transcripts/LIVE_{spec['label']}.txt"
        open(out,'w').write('\n\n'.join(textos) + '\n')
        print(f'live-style: {len(chunks)} chunks em {(time.time()-t0)/60:.1f}min | {out}')
    else:
        _lang = spec.get('language','pt') or None
        if _lang == 'auto': _lang = None
        segs, info = m.transcribe('work/cut.wav', language=_lang, vad_filter=True, beam_size=5)
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
