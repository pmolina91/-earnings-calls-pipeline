# Processo: nunca mais perder o começo de um call

## Por que perdíamos o começo (padrão recorrente)
Sempre a mesma forma de falha, em uma destas três:
1. **Ativação não dispara** — o cron agendado do GitHub Actions é não-confiável (o 1º run de um workflow novo costuma ser atrasado/pulado). Foi o que aconteceu no Santander (2T26).
2. **Morte na transição sala-de-espera → ao vivo** — o runner entra ANTES do host, pega áudio de espera (música/silêncio, ~-38/-40 dB), e quando o host inicia o webinar o caminho de áudio quebra e a captura morre. TIM (2T26) e SANB (2T26) morreram assim.
3. **Resgate manual entra tarde** — o resgate salva o call, mas por definição entra depois do início e perde a abertura.

**Conclusão de design:** a garantia de "nunca perder o começo" NÃO pode depender do runner que entra antes do host. Precisa ser estrutural e redundante.

## As 5 camadas (defesa em profundidade)

### Camada 0 — Ativação confiável (não confiar no cron do GitHub)
- **Guardião de ativação** (tarefa agendada do Claude, T-50min): abre a aba Actions e verifica se o run de captura de hoje existe e está *in progress*. Se **não**, dispara o workflow (`Run workflow` / workflow_dispatch) na hora. O cron nativo do GitHub vira só backup.
- Regra operacional: **na véspera/manhã do call, confirmar na aba Actions que o run apareceu; se não, disparar manual.** (Foi assim que salvamos o SANB.)

### Camada 1 — Dois runners escalonados (um SEMPRE entra ao vivo)
Dois specs por call, controlados pelo campo `join_offset_seconds` (implementado no `capture.py`):
- **Runner CEDO** (`join_offset_seconds: -600` = T-10): tenta capturar 100%, inclusive a abertura. Agora endurecido (Camada 2) para sobreviver à transição.
- **Runner AO VIVO** (`join_offset_seconds: +120` = T+2): entra com o call **já iniciado** → estruturalmente **nunca cai na sala de espera** nem sofre a transição que mata o CEDO. Garante que temos o call a partir de ~T+2 mesmo se o CEDO morrer.
- Ambos já ficam instalados e esperando ANTES do call; entram nos seus offsets. Publicação ao vivo no Notion: só um publica (o CEDO); o AO VIVO grava em `transcripts/raw/` como backup silencioso. Pós-call o cérebro mescla (abertura do que sobreviver; resto do melhor áudio).

### Camada 2 — `capture.py` que não morre e re-arma o áudio
Implementado:
- **Nunca encerra por silêncio** — só no `t_end` (max_capture_minutes) ou sinal `END` externo.
- **Re-arma o áudio a cada 20s**: `pactl set-default-sink cap` + re-clica "Entrar por áudio do computador"/play + desmuta os elementos `<audio>/<video>`. Isso mantém o áudio fluindo através da transição sala-de-espera→ao vivo.
- **Reinicia o ffmpeg travado**: se não há chunk novo por ~100s, mata e reinicia a gravação sem perder a numeração (`-segment_start_number`).

### Camada 3 — Watchdog que distingue FALA de música de espera
Implementado no `audio_watchdog.py`:
- `SOM_OK` só é declarado com **fala real** (`mean_volume > -33 dB`) **e já no/após o horário do call** — não é mais enganado pela música de espera (~-39 dB, como no SANB).
- Se não houver fala real até **T+180s**, commita o marcador **`PRECISA_RESGATE`** (sinal legível por máquina).

### Camada 4 — Resgate automático (sem humano no loop)
- Guardião T+3min (tarefa agendada do Claude) lê o repo: se houver `PRECISA_RESGATE` **ou** não houver transcrição real fluindo, **dispara automaticamente o runner AO VIVO de resgate** (`join_offset` negativo → entra imediato). Repete uma vez em T+6 se ainda nada.
- Como o Runner AO VIVO da Camada 1 já cobre isso estruturalmente, este é a rede de segurança adicional.

### Camada 5 — Backfill pelo áudio OFICIAL do RI (a espinha dorsal da completude)
A garantia final. O áudio/replay oficial do RI contém o call **inteiro, inclusive a abertura**.
- Tarefa agendada (T+3h e re-tentativas) verifica o site de RI / MZ pela gravação oficial; quando disponível, **reprocessa o call inteiro** (`test_replay.py` → `finalize`/`format_transcript`) e **substitui/completa** a transcrição ao vivo na nota.
- Assim, **a nota arquivada é sempre completa**, independentemente de qualquer falha da captura ao vivo. A captura ao vivo passa a ser "velocidade no dia"; o replay oficial é a **fonte da verdade para completude**.

## Fluxo operacional por call (checklist)
1. **D-1**: gerar os 2 specs (CEDO + AO VIVO) via `scripts/make_dual_jobs.py staging/{TICKER}.json`; confirmar `join_url`/`webinar_id`.
2. **T-50min** (guardião): confirmar/disparar o run na aba Actions.
3. **T-10 / T+2**: runners entram; watchdog valida FALA REAL após T-0.
4. **T+3** (guardião): se `PRECISA_RESGATE` → dispara resgate AO VIVO automático.
5. **Durante**: transcrição ao vivo publica no Notion (uma página por call).
6. **T+3h** (backfill): reprocessa do áudio oficial do RI → nota completa (inclui abertura).
7. **Pós**: cérebro monta a nota no padrão (Resumo + vs. anterior + transcrição por interlocutor + Q&A) — skill `nota-pos-call-resultado`.

## Resumo de "por que agora não perde mais"
- A **completude** é garantida pelo **replay oficial** (Camada 5), que sempre tem a abertura — não depende da captura ao vivo.
- A **velocidade** (ler ao vivo) é garantida pelo **runner AO VIVO** (Camada 1), que nunca cai na espera, + `capture.py` que não morre (Camada 2).
- A **ativação** não depende mais do cron frágil (Camada 0), e há **resgate automático** (Camada 4) se o áudio real não aparecer.
