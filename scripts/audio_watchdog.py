#!/usr/bin/env python3
"""Watchdog de audio: a cada 30s sonda o volume da captura.
Distingue FALA REAL de musica de espera/silencio:
 - SOM (qualquer): mean_volume > LIMIAR_SOM
 - FALA REAL: mean_volume > LIMIAR_FALA (mais alto) — musica de espera fica abaixo disso
SOM_OK so' e' declarado com FALA REAL e ja' no/apos o horario do call (nao ser enganado pela espera).
Se nao houver FALA REAL ate' T+PRAZO_RESGATE apos o inicio, commita PRECISA_RESGATE (sinal p/ resgate
automatico via runner 'ao vivo'). Re-alerta a cada 5 min de silencio; SOM_RETOMADO quando voltar."""
import os, sys, time, subprocess, re, glob
from datetime import datetime, timezone

MODO = sys.argv[1] if len(sys.argv) > 1 else 'pulse'   # pulse | hls
TICKER = sys.argv[2] if len(sys.argv) > 2 else '?'
CALL_UTC = sys.argv[3] if len(sys.argv) > 3 else ''
RID = os.environ.get('GITHUB_RUN_ID', 'local')
LIMIAR_SOM = -45.0    # acima disso = tem algum som
LIMIAR_FALA = -33.0   # acima disso = fala real (musica de espera costuma ficar em ~-38/-40dB)
PRAZO_RESGATE = 180   # s apos o inicio do call sem FALA REAL -> pede resgate
os.makedirs('logs', exist_ok=True)

def _call_start():
    try:
        return datetime.fromisoformat(CALL_UTC.replace('Z','+00:00'))
    except Exception:
        return None
CALL = _call_start()

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

def apos_inicio():
    if CALL is None: return True
    return datetime.now(timezone.utc) >= CALL

t0 = time.time()
fala_ok = False           # ja' confirmamos fala real (SOM_OK)
pediu_resgate = False
silencio_desde = None
ultimo_alerta = 0
while not os.path.exists('work/audio/END') and time.time() - t0 < 3*3600:
    time.sleep(30)
    db = volume_db()
    tem_som = db is not None and db > LIMIAR_SOM
    tem_fala = db is not None and db > LIMIAR_FALA
    ts = time.strftime('%H:%M:%SZ', time.gmtime())
    print(f'[watchdog] {ts} mean_volume={db} som={tem_som} fala_real={tem_fala} apos_inicio={apos_inicio()}', flush=True)

    # SOM_OK: exige FALA REAL e ja' estar no/apos o horario do call (nao contar musica de espera)
    if not fala_ok and tem_fala and apos_inicio():
        fala_ok = True
        commit('SOM_OK', f'{ts} FALA REAL confirmada mean_volume={db}dB')
        silencio_desde = None

    # PRECISA_RESGATE: passou do inicio + PRAZO e nunca houve fala real -> sinal p/ resgate automatico
    if (not fala_ok and not pediu_resgate and CALL is not None
            and datetime.now(timezone.utc).timestamp() - CALL.timestamp() > PRAZO_RESGATE):
        pediu_resgate = True
        commit('PRECISA_RESGATE', f'{ts} sem fala real ate T+{PRAZO_RESGATE}s (mean_volume={db}dB) — '
               f'captura provavelmente na pagina/espera errada; disparar runner AO VIVO (join_offset +120).')
        silencio_desde = time.time(); ultimo_alerta = time.time()

    # apos ter fala: monitora quedas de silencio
    if fala_ok:
        if tem_fala:
            if silencio_desde and time.time() - silencio_desde > 120:
                commit('SOM_RETOMADO', f'{ts} fala voltou mean_volume={db}dB')
            silencio_desde = None
        else:
            if silencio_desde is None: silencio_desde = time.time()
            if time.time() - ultimo_alerta > 300:
                commit('ALERTA_SILENCIO', f'{ts} silencio ha {int(time.time()-silencio_desde)}s (mean_volume={db}dB)')
                ultimo_alerta = time.time()
