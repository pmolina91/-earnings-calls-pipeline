# earnings-calls-pipeline

Captura, transcrição (PT) e publicação no Notion de calls de resultado de empresas da B3 — 100% automatizado e gratuito (GitHub Actions).

## Como funciona
1. O orquestrador (Claude/Cowork na nuvem) mantém o calendário de resultados (fonte: sites de RI) e, na véspera de cada call, faz `git push` de um job spec em `jobs/` com horário, link do webcast e destino no Notion.
2. O push dispara o workflow `capture-earnings-call`, que valida a janela, espera até T-10min, entra no webcast se registrando com a identidade configurada (secrets), grava o áudio em chunks de 2min e transcreve ao vivo (faster-whisper small, PT), publicando incrementalmente na página do call no Notion.
3. Ao fim, re-transcreve o áudio inteiro com mais qualidade, publica a versão final consolidada, commita a transcrição em `transcripts/` e guarda o áudio como artifact (90 dias).

## Secrets necessários (Settings → Secrets and variables → Actions)
- `NOTION_TOKEN` — token de integração interna do Notion com acesso às páginas das empresas
- `REG_NAME`, `REG_EMAIL`, `REG_COMPANY` — identidade usada nos formulários de registro dos webcasts

## Formato do job spec (jobs/TICKER_TRIMESTRE.json)
Ver `jobs/EXEMPLO.json`.

## Robustez
- Gate de janela temporal (não roda jobs velhos/re-pushes)
- Duas estratégias de gravação: stream direto (HLS/DASH sniffado) e áudio de aba via PulseAudio (Zoom etc.)
- Live loop tolerante a falha por chunk; versão final cobre qualquer buraco do ao vivo
- Fim por sentinela ou 10min de silêncio; timeout máximo 6h
- Transcrição final versionada no git (auditável) + áudio em artifact

Aprendizados e evolução: mantidos no projeto Equities (Claude) e nas issues deste repo.
