#!/usr/bin/env python3
"""Watchdog de audio: a cada 30s sonda o volume da captura.
~60s apos o inicio: commita SOM_OK (primeiro som real) ou ALERTA_SILENCIO.
Depois: re-alerta a cada 5 min de silencio continuo; SOM_RETOMADO quando voltar."""
import os, sys, time, subprocess, re, glob

MODO = sys.argv[1] if len(sys.argv) > 1 else 'pulse'   # pulse | hls
TICKER = sys.argv[2] if len(sys.argv) > 2 else '?'
RID = os.environ.get('GITHUB_RUN_ID', 'local')
LIMIAR_DB = -45.0   # mean_volume acima disso = tem som
os.makedirs('logs', exist_ok=True)

def commit(nome, texto):
    try:
        with open(f'logs/{nome}_{RID}.txt', 'a') as f:
            f.write(texto + '\n')
        subprocess.run(['git','config','user.name','earnings-bot'])
        subprocess.run(['git','config','user.email','bot@users.noreply.github.com'])
        for i in (1,2,3):
            subprocess.run(['git','pull','-q','--rebase'])
            subprocess.run(['git','add','logs/'])
            ok = subprocess.run(['git','commit','-q','-m',f'{nome} {TICKER}']).returncode == 0
            if ok and subprocess.run(['git','push','-q']).returncode == 0: return
            time.sleep(i*5)
    except Exception as e:
        print(f'[watchdog] erro commit: {e}', flush=True)

def volume_db():
    """mean_volume em dB da sonda de 8s (pulse) ou do ultimo chunk (hls)."""
    try:
        if MODO == 'pulse':
            subprocess.run(['ffmpeg','-y','-loglevel','error','-f','pulse','-i','cap.monitor',
                            '-t','8','work/probe.wav'], timeout=20)
            alvo = 'work/probe.wav'
        else:
            chunks = sorted(glob.glob('work/audio/chunk_*.wav'))
            if not chunks: return None
            alvo = chunks[-1]
        r = subprocess.run(['ffmpeg','-i',alvo,'-af','volumedetect','-f','null','-'],
                           capture_output=True, text=True, timeout=30)
        m = re.search(r'mean_volume:\s*(-?[\d.]+) dB', r.stderr)
        return float(m.group(1)) if m else None
    except Exception:
        return None

t0 = time.time()
primeiro_veredito = False
silencio_desde = None
ultimo_alerta = 0
while not os.path.exists('work/audio/END') and time.time() - t0 < 3*3600:
    time.sleep(30)
    db = volume_db()
    tem_som = db is not None and db > LIMIAR_DB
    ts = time.strftime('%H:%M:%SZ', time.gmtime())
    print(f'[watchdog] {ts} mean_volume={db} som={tem_som}', flush=True)
    if not primeiro_veredito and time.time() - t0 >= 55:
        primeiro_veredito = True
        if tem_som:
            commit('SOM_OK', f'{ts} primeiro som confirmado mean_volume={db}dB')
        else:
            commit('ALERTA_SILENCIO', f'{ts} SEM SOM no 1o minuto (mean_volume={db}dB) — captura provavelmente na pagina errada')
            silencio_desde = time.time(); ultimo_alerta = time.time()
    elif primeiro_veredito:
        if tem_som:
            if silencio_desde and time.time() - silencio_desde > 120:
                commit('SOM_RETOMADO', f'{ts} som voltou mean_volume={db}dB')
            silencio_desde = None
        else:
            if silencio_desde is None: silencio_desde = time.time()
            if time.time() - ultimo_alerta > 300:
                commit('ALERTA_SILENCIO', f'{ts} silencio ha {int(time.time()-silencio_desde)}s (mean_volume={db}dB)')
                ultimo_alerta = time.time()
