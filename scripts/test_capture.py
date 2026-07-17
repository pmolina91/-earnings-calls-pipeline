#!/usr/bin/env python3
"""Teste de captura de áudio de página (como num webcast), com lista de candidatos.
Para cada candidato (page_url ou direct_audio_url), tenta capturar `duration_seconds`
de áudio em chunks de 60s: página → estratégia A (sniff de stream + ffmpeg) ou
B (PulseAudio, áudio da aba, headful sob xvfb); direto → ffmpeg na URL.
Para no primeiro candidato com áudio de verdade. Transcreve chunk a chunk (small,
como no ao vivo) e escreve transcrição + relatório. Erros em work/error.txt."""
import json, sys, os, time, re, subprocess, traceback, glob

MEDIA_RE = re.compile(r'\.(m3u8|mpd|mp3|aac)(\?|$)')

def limpar():
    os.makedirs('work/audio', exist_ok=True)
    for x in glob.glob('work/audio/*'):
        os.remove(x)

def captura_ok():
    chunks = sorted(glob.glob('work/audio/chunk_*.wav'))
    return bool(chunks) and any(os.path.getsize(x) > 100_000 for x in chunks)

def gravar_direct(url, dur, report):
    report['strategy'] = 'direct_ffmpeg'
    subprocess.run(['ffmpeg', '-loglevel', 'warning', '-i', url, '-vn', '-ac', '1', '-ar', '16000',
                    '-f', 'segment', '-segment_time', '60', '-reset_timestamps', '1',
                    '-t', str(dur), 'work/audio/chunk_%03d.wav'], timeout=dur + 90)

def gravar_pagina(page_url, dur, report, force_pulse=False):
    report['_force_pulse'] = force_pulse
    from playwright.sync_api import sync_playwright
    media = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False,
            ignore_default_args=['--mute-audio'],
            args=['--autoplay-policy=no-user-gesture-required', '--no-sandbox', '--disable-dev-shm-usage'])
        page = browser.new_context(locale='pt-BR').new_page()
        page.on('request', lambda r: media.append(r.url) if MEDIA_RE.search(r.url) and len(media) < 5 else None)
        page.goto(page_url, timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        for s in ['button[aria-label*=play i]', 'button[title*=play i]', '.play',
                  'button:has-text("Ouvir")', 'button:has-text("Play")', 'video', 'audio']:
            try:
                page.locator(s).first.click(timeout=2000)
                report['notes'].append(f'click:{s}')
                break
            except Exception:
                pass
        time.sleep(10)
        report['media_urls'] = [u[:120] for u in media]
        if media and not report.get('_force_pulse'):
            report['strategy'] = 'sniff_ffmpeg'
            p = subprocess.Popen(['ffmpeg', '-loglevel', 'warning', '-i', media[0], '-vn', '-ac', '1',
                '-ar', '16000', '-f', 'segment', '-segment_time', '60', '-reset_timestamps', '1',
                '-t', str(dur), 'work/audio/chunk_%03d.wav'])
        else:
            report['strategy'] = 'pulse_tab_audio'
            p = subprocess.Popen(['ffmpeg', '-loglevel', 'warning', '-f', 'pulse', '-i', 'cap.monitor',
                '-ac', '1', '-ar', '16000', '-f', 'segment', '-segment_time', '60', '-reset_timestamps', '1',
                '-t', str(dur), 'work/audio/chunk_%03d.wav'])
        try:
            p.wait(timeout=dur + 120)
        finally:
            try: p.kill()
            except Exception: pass
        browser.close()

def main():
    spec = json.load(open(sys.argv[1]))
    dur = int(spec.get('duration_seconds', 240))
    candidatos = spec.get('candidates') or [{'page_url': spec['page_url']}]
    report = {'strategy': None, 'candidato': None, 'media_urls': [], 'chunks': [], 'notes': []}

    subprocess.run(['pulseaudio', '--start', '--exit-idle-time=-1'], check=False)
    subprocess.run(['pactl', 'load-module', 'module-null-sink', 'sink_name=cap',
                    'sink_properties=device.description=cap'], check=False)
    subprocess.run(['pactl', 'set-default-sink', 'cap'], check=False)

    for cand in candidatos:
        limpar()
        alvo = cand.get('direct_audio_url') or cand.get('page_url')
        report['notes'].append(f'tentando: {alvo[:100]}')
        try:
            if cand.get('direct_audio_url'):
                gravar_direct(cand['direct_audio_url'], dur, report)
            else:
                gravar_pagina(cand['page_url'], dur, report, force_pulse=spec.get('force_pulse', False))
        except Exception as e:
            report['notes'].append(f'falhou: {str(e)[:200]}')
            continue
        if captura_ok():
            report['candidato'] = alvo[:120]
            break
        report['notes'].append('sem áudio útil, próximo candidato')

    chunks = sorted(glob.glob('work/audio/chunk_*.wav'))
    report['chunks'] = [{'f': os.path.basename(c), 'kb': os.path.getsize(c) // 1024} for c in chunks]

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
        f"# TESTE de captura de página — {lbl}\n\nEstratégia: {report['strategy']} | Fonte: {report['candidato']}\n\n"
        + '\n\n'.join(textos) + '\n')
    open(f'transcripts/CAPTURA_{lbl}_relatorio.json', 'w').write(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps(report, indent=1, ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except Exception:
        os.makedirs('work', exist_ok=True)
        open('work/error.txt', 'w').write(traceback.format_exc())
        print(traceback.format_exc())
        sys.exit(1)
