#!/usr/bin/env python3
"""Teste da captura de áudio de PÁGINA (como num webcast): abre a URL num Chromium
com áudio real (headful sob xvfb), tenta 2 estratégias:
  A) sniffing: se a página carrega stream (m3u8/mpd/mp3/aac), grava via ffmpeg direto
  B) PulseAudio: sink virtual captura o áudio da aba (caminho tipo-Zoom)
Grava duration_seconds em chunks de 60s, transcreve cada chunk (como no ao vivo)
e escreve transcrição + relatório. Erros vão para work/error.txt."""
import json, sys, os, time, re, subprocess, traceback

def main():
    spec = json.load(open(sys.argv[1]))
    os.makedirs('work/audio', exist_ok=True)
    dur = int(spec.get('duration_seconds', 240))
    report = {'strategy': None, 'media_urls': [], 'chunks': [], 'notes': []}

    # PulseAudio: sink virtual ANTES do browser
    subprocess.run(['pulseaudio', '--start', '--exit-idle-time=-1'], check=False)
    subprocess.run(['pactl', 'load-module', 'module-null-sink', 'sink_name=cap',
                    'sink_properties=device.description=cap'], check=False)
    subprocess.run(['pactl', 'set-default-sink', 'cap'], check=False)

    from playwright.sync_api import sync_playwright
    MEDIA_RE = re.compile(r'\.(m3u8|mpd|mp3|aac)(\?|$)')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False,
            ignore_default_args=['--mute-audio'],
            args=['--autoplay-policy=no-user-gesture-required', '--no-sandbox',
                  '--disable-dev-shm-usage'])
        page = browser.new_context(locale='pt-BR').new_page()
        page.on('request', lambda r: report['media_urls'].append(r.url)
                if MEDIA_RE.search(r.url) and len(report['media_urls']) < 5 else None)
        page.goto(spec['page_url'], timeout=90000, wait_until='domcontentloaded')
        time.sleep(8)
        # tentar clicar em play se existir
        for s in ['button[aria-label*=play i]', 'button[title*=play i]', '.play', 'button:has-text("Ouvir")',
                  'button:has-text("Play")', 'video', 'audio']:
            try:
                page.locator(s).first.click(timeout=2000); report['notes'].append(f'click:{s}'); break
            except Exception: pass
        time.sleep(10)

        rec = None
        if report['media_urls']:
            report['strategy'] = 'sniff_ffmpeg'
            url = report['media_urls'][0]
            rec = subprocess.Popen(['ffmpeg', '-loglevel', 'warning', '-i', url, '-vn',
                '-ac', '1', '-ar', '16000', '-f', 'segment', '-segment_time', '60',
                '-reset_timestamps', '1', '-t', str(dur), 'work/audio/chunk_%03d.wav'])
        else:
            report['strategy'] = 'pulse_tab_audio'
            rec = subprocess.Popen(['ffmpeg', '-loglevel', 'warning', '-f', 'pulse', '-i', 'cap.monitor',
                '-ac', '1', '-ar', '16000', '-f', 'segment', '-segment_time', '60',
                '-reset_timestamps', '1', '-t', str(dur), 'work/audio/chunk_%03d.wav'])
        rec.wait(timeout=dur + 120)
        browser.close()

    import glob
    chunks = sorted(glob.glob('work/audio/chunk_*.wav'))
    report['chunks'] = [{'f': os.path.basename(c), 'kb': os.path.getsize(c)//1024} for c in chunks]
    if not chunks or all(os.path.getsize(c) < 50000 for c in chunks):
        report['notes'].append('AUDIO VAZIO OU MUITO PEQUENO')
    # transcrição chunk a chunk (simulando o ao vivo)
    from faster_whisper import WhisperModel
    m = WhisperModel('models/faster-whisper-small', device='cpu', compute_type='int8')
    textos, t0 = [], time.time()
    for c in chunks:
        try:
            segs, _ = m.transcribe(c, language='pt', vad_filter=True, beam_size=2)
            t = ' '.join(s.text.strip() for s in segs).strip()
            textos.append(t)
            report['notes'].append(f'{os.path.basename(c)}: {len(t)} chars')
        except Exception as e:
            report['notes'].append(f'{os.path.basename(c)}: ERRO {e}')
    report['transcricao_total_chars'] = sum(len(t) for t in textos)
    report['tempo_transcricao_s'] = round(time.time() - t0)
    os.makedirs('transcripts', exist_ok=True)
    lbl = spec['label']
    open(f'transcripts/CAPTURA_{lbl}.md', 'w').write(
        f"# TESTE de captura de página — {lbl}\n\nEstratégia: {report['strategy']}\n\n" +
        '\n\n'.join(textos) + '\n')
    open(f'transcripts/CAPTURA_{lbl}_relatorio.json', 'w').write(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps(report, indent=1, ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except Exception:
        os.makedirs('work', exist_ok=True)
        open('work/error.txt', 'w').write(traceback.format_exc())
        print(traceback.format_exc()); sys.exit(1)
