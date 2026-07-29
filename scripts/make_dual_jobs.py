#!/usr/bin/env python3
"""Gera os DOIS specs escalonados de um call a partir de um spec de staging.
 - {TICKER}_CEDO.json : join_offset_seconds=-600 (T-10), publica ao vivo no Notion.
 - {TICKER}_VIVO.json : join_offset_seconds=+120 (T+2), entra JA' AO VIVO (nunca cai na espera),
                        notion=false (backup silencioso: so' audio + raw).
Uso: python3 scripts/make_dual_jobs.py staging/SANB11_2T26.json  [dir_saida=jobs]
Ver docs/PROCESSO-captura.md (Camada 1)."""
import json, sys, os

src = sys.argv[1]
outdir = sys.argv[2] if len(sys.argv) > 2 else 'jobs'
spec = json.load(open(src))
os.makedirs(outdir, exist_ok=True)
base = spec.get('ticker_short') or spec.get('ticker') or os.path.splitext(os.path.basename(src))[0]

cedo = dict(spec); cedo['join_offset_seconds'] = -600; cedo['notion'] = True
vivo = dict(spec); vivo['join_offset_seconds'] = 120;  vivo['notion'] = False  # backup silencioso
vivo['max_capture_minutes'] = min(int(spec.get('max_capture_minutes', 180)), 180)

for suf, s in [('CEDO', cedo), ('VIVO', vivo)]:
    p = os.path.join(outdir, f'{base}_{suf}.json')
    json.dump(s, open(p, 'w'), ensure_ascii=False, indent=1)
    print('gerado:', p, '(join_offset', s['join_offset_seconds'], 'notion', s['notion'], ')')
print('\nAtive commitando UM por vez (regra da deteccao de spec) OU rode-os como matriz no '
      'workflow dedicado. O CEDO publica ao vivo; o VIVO e backup que garante a captura ao vivo.')
