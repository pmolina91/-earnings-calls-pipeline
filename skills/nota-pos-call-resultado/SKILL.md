---
name: "nota-pos-call-resultado"
description: "Reescrever/estruturar a nota de um conference call de resultado DEPOIS que ele termina e é transcrito: transcrição final legível (por interlocutor, sem timestamps, termos corrigidos), Resumo do Call + comparativo vs. o call anterior no início, e Q&A formatado no fim. Use quando um call de resultado foi concluído e transcrito e o usuário quer a nota do analista pronta no Notion (UMA página por call). Padrão da mesa buy-side — feito para ser compartilhado entre analistas."
---

# Nota pós-call de resultado (buy-side)

Transforma a transcrição bruta de um conference call de resultado numa **nota de analista** pronta para leitura, dentro do Notion. É o passo do "cérebro" que roda **depois** que o call terminou e a transcrição já está na página.

Resultado final, numa **única** página por call, nesta ordem de cima para baixo:

1. `📌 Resumo do Call — principais pontos do Q&A` (bullets dos destaques)
2. `🔁 vs. call anterior (NT{AA})` (o que mudou e o que ficou constante)
3. `---`
4. `Transcrição final (por interlocutor)` — **legível, sem timestamps, fala separada por pessoa, termos corrigidos** (ver Passo 2). A versão **ao vivo** deve ter sido **apagada**.
5. `---`
6. `📋 Q&A formatado — N perguntas` (pergunta por analista/banco + resposta por executivo)

## Princípios invioláveis
- **UMA página por call.** Nunca crie uma segunda nota para o mesmo call. Se a página já existe (o normal, pois a captura ao vivo já criou), edite-a. Use `notion-search`/`find_call_page` pelo título (`Call {N}T{AA} - {TICKER}`).
- **Transcrição no idioma original** (não traduzir). O Resumo e o Q&A formatado saem em **PT-BR** para leitura rápida da mesa.
- **Nada de timestamps** na transcrição que o analista lê. Timestamps só ficam no arquivo raw interno do repo (`transcripts/raw/`).
- **Fala separada por interlocutor.** O leitor tem que saber quem fala: operador, cada analista (nome + banco) e cada executivo (nome + cargo).
- **Frases inteiras.** Nunca deixe a frase quebrada no meio (artefato de captura em blocos). Junte os segmentos num parágrafo corrido por turno de fala.
- **Termos corrigidos.** Conserte transcrições erradas de jargão (ex.: "VITDA"→EBITDA, "vektor"→vetor, "cresção"→geração, "alfa"→trimestre quando o contexto é "1º/2º alfa", "neta"→net, "profilação"→perfil). Não invente número/guidance/nome.
- **Fidelidade acima de fluência.** Se a separação de turnos ou a atribuição de fala for incerta, rotule "Interlocutor?" em vez de chutar.
- **Sempre separe seções** com `---`.

## Passo 1 — Localizar a página e a transcrição
1. `notion-search` pelo título do call (`Call {N}T{AA} - {TICKER}`) e/ou pela empresa. Pegue o `page_id`.
2. `notion-fetch` a página. Se estiver grande, o fetch vem paginado — leia por partes até cobrir todo o Q&A e saber o que já existe (não duplicar Resumo/Q&A).
3. Fontes possíveis da transcrição, em ordem de preferência: (a) `transcripts/{TICKER}_{Q}.md` do repo (já vem final, por interlocutor — pode só precisar de revisão); (b) o raw com timestamps em `transcripts/raw/`; (c) o áudio oficial do RI publicado depois (melhor qualidade — reprocessar via replay quando disponível).

## Passo 2 — Produzir a transcrição FINAL legível (por interlocutor)
O `finalize.py` já entrega uma primeira versão via `scripts/format_transcript.py` (heurística operador→analista→executivo + glossário). O seu papel de cérebro é **revisar e corrigir**:
1. **Conferir a atribuição de fala** contra o conteúdo — a heurística erra transições. Corrija quem está falando (o operador anuncia "pergunta de {Analista} do {Banco}"; o executivo costuma se auto-identificar "aqui é o {Nome}", "that's {Name}").
2. **Corrigir termos** que a heurística não pega (contextual): números, nomes de produto, jargão. Use o release oficial para casar números.
3. **Garantir frases inteiras**: nada de corte no meio.
4. Formato de cada turno: `**🎙️ Operador:** …`, `**❓ {Analista} ({Banco}):** …`, `**💬 {Executivo} ({cargo}):** …`.
5. **Apagar a transcrição ao vivo** (com timestamps/blocos quebrados) se ela ainda estiver na página. Em código, `notion_api.delete_live_blocks(page_id)` faz isso preservando Resumo/Q&A; manualmente, remova os blocos sob "Transcrição (ao vivo)".

> Para calls **bilíngues** (analistas em inglês, companhia em português, ou vice-versa), o Whisper forçado a um idioma degrada a outra parte. Prefira reprocessar do áudio oficial do RI, ou sinalize os trechos degradados em vez de publicar jargão errado.

## Passo 3 — Montar o `📌 Resumo do Call` (topo)
6–8 bullets com os **temas centrais do Q&A**. Cada bullet: tema em **negrito**, quem puxou (Analista, Banco), e a síntese da resposta.

```markdown
# 📌 Resumo do Call — principais pontos do Q&A
- **{Tema}** ({Analista}, {Banco}): {síntese da resposta com números preservados}.
- ... (5 a 7 bullets adicionais)
```

## Passo 4 — Montar o `🔁 vs. call anterior`
1. Localize a nota do trimestre anterior (`notion-search "Call {N-1}T{AA} - {TICKER}"`). Se existir, leia Resumo/Q&A.
2. Bullets de **o que MUDOU** e **o que ficou CONSTANTE**, em duas dimensões: **dúvidas dos analistas** (temas que entraram/saíram) e **discurso da companhia** (tom, guidance, ênfase).
3. Se não houver nota anterior arquivada, marque explícito:

```markdown
## 🔁 vs. call anterior ({N-1}T{AA})
> *Não disponível — primeira nota de call arquivada desta empresa. A partir do próximo trimestre, esta seção trará o comparativo.*
```

Com base de comparação:
```markdown
## 🔁 vs. call anterior ({N-1}T{AA})
**Mudou:**
- **Dúvidas:** {tema} entrou / {tema} saiu da pauta.
- **Discurso:** companhia passou a enfatizar {…}; mudança de tom em {…}.
**Constante:**
- {tema recorrente} e {mensagem repetida pela cia}.
```

## Passo 5 — Montar o `📋 Q&A formatado` (fim)
Um bloco por analista. **Separe P1, P2, …** como sub-bullets. Resposta em bullets, atribuída ao executivo (cargo).

```markdown
---
# 📋 Q&A formatado — {N} perguntas

❓ **Pergunta 1 — {Analista} ({Banco})**
- **P1:** {pergunta 1}
- **P2:** {pergunta 2}

💬 **Resposta — {Executivo} ({cargo})**
- {ponto 1, com números/guidance preservados}
- {ponto 2}
```
No fim, `💬 **Encerramento — {Executivo} ({cargo})**` com os pontos de fechamento, se houver.

## Passo 6 — Escrever no Notion (sem duplicar)
- **Resumo + vs. anterior** no **início**: `notion-update-page` `insert_content` com `position:{"type":"start"}`, terminando com `---`.
- **Transcrição final**: publique após apagar a ao vivo (ver Passo 2). Em pipeline, o `finalize.py` já faz isso.
- **Q&A formatado** no **fim**: `insert_content` com `position:{"type":"end"}`, começando com `---`.
- Correções pontuais: `update_content` com `content_updates` (old_str/new_str exatos).
- Ajuste o título para a versão final (sem "[LIVE …]").

## Passo 7 — Verificação final
- Ordem na página: Resumo → vs. anterior → transcrição final (por interlocutor, sem timestamps) → Q&A formatado.
- Nenhum bloco da transcrição ao vivo sobrou; nenhuma frase cortada no meio.
- Termos de jargão corrigidos; números batem com o release.
- Contagem de perguntas do cabeçalho bate com os blocos; **não há segunda página** para o call.

## Notas técnicas
- Correção mecânica de termos e separação por interlocutor: `scripts/format_transcript.py` (`to_speaker_text`, `corrige_termos`, `limpa`). Aceita glossário por empresa (`spec["glossario"]`: `{regex: substituição}`).
- Apagar ao vivo: `notion_api.delete_live_blocks(page_id)` (preserva Resumo/Q&A).
- Datas no Notion: `date:Data:start` + `date:Data:is_datetime` (0/1). Faça `notion-fetch` no data source para os nomes exatos das propriedades.

## Compartilhar com outros analistas
Genérica (qualquer empresa/analista/banco). Fica versionada no repo em `skills/nota-pos-call-resultado/`. Para distribuir: copie a pasta para o diretório de skills de cada analista ou empacote num plugin da Cowork.
