#!/usr/bin/env python3
"""Formata uma transcricao (lista de segmentos) num texto legivel SEM timestamps,
separando a fala por interlocutor via heuristica de call de resultado:
operador (moderador) -> analista (nome/banco) -> executivo.

A atribuicao e' APROXIMADA (audio mono, sem diarizacao real). O passo do 'cerebro'
(skill nota-pos-call-resultado) revisa e corrige os rotulos. Melhor um texto ja
quebrado por turnos do que um paredao de texto com timestamps.
"""
import re

# frases que SO' o operador/moderador diz (evitar "first/second question" que o analista tambem fala)
OPERADOR_CUES = [
    'question comes from', 'next question comes', 'question is from',
    'floor is now yours', 'floor is yours', 'you may now speak', 'you may speak',
    'your microphone is', 'your line is open', 'line is now open', 'please go ahead',
    'questions and answers section is over', 'questions and answers session',
    'we will now begin the', 'we will now take', 'hand the floor', 'hand it back',
    'conference is now closed', 'that concludes', 'star one',
    # portugues (operador de teleconferencia BR)
    'pergunta vem d', 'pergunta, vem d', 'primeira pergunta vem', 'proxima pergunta vem',
    'a palavra esta com', 'a palavra ao', 'a palavra para o', 'a palavra para a',
    'a palavra a ', 'passo a palavra', 'devolvo a palavra', 'seu microfone esta',
    'sessao de perguntas e respostas', 'esta encerrada', 'agradecemos a participacao',
    'consideracoes finais', 'nossa primeira pergunta',
]

# executivo assumindo a resposta (inicio de resposta)
EXEC_START = [
    'thank you for your question', 'thank you for the question', 'thanks for the question',
    'thank you for your comments', 'thanks for your question', 'thank you for the questions',
    'obrigado pela pergunta', 'obrigado pela sua pergunta', 'obrigado pelas perguntas',
]

_STOP = {'good','more','for','the','and','you','okay','well','yes','yeah','here','there',
         'that','this','compared','comparable','going','questions','question','thank','thanks',
         'hello','sorry','now','then','first','second','your','our','regarding','again','actually',
         'although','overall','no','so','but','very','clear','great','morning'}

# auto-identificacao FORTE do executivo (nome proprio capitalizado, nao-stopword)
_NAME = r"([A-Z][a-zçãáéíóâêõà]{2,})"
_SELFID = [
    re.compile(r"\bthis is " + _NAME),
    re.compile(r"\bthat'?s " + _NAME),
    re.compile(_NAME + r" here[\.,\b]"),
    re.compile(r"\bcan " + _NAME + r" (?:have an answer|answer|take)", re.I),
    re.compile(r"\baqui (?:e|eh|é) o " + _NAME),
    # PT: "André Rodrigues falando aqui" — exige nome+sobrenome (evita "Estamos falando")
    re.compile(r"\b([A-Z][a-zà-ú]+ [A-Z][a-zà-ú]+) falando"),
]

_norm = lambda s: re.sub(r'[^a-z ]', '', (s or '').lower())

# subconjunto: pistas que iniciam uma PERGUNTA (vs. hand-off entre executivos na apresentacao)
QUESTION_CUES = [
    'question comes from', 'next question comes', 'question is from', 'floor is now yours',
    'floor is yours', 'you may now speak', 'you may speak', 'your microphone is',
    'pergunta vem d', 'pergunta, vem d', 'primeira pergunta vem', 'proxima pergunta vem',
    'nossa primeira pergunta', 'a palavra esta com',
]

# correcoes de termos claramente errados (nao-palavras). O grosso da correcao
# contextual e' do 'cerebro' (skill); aqui so' o obvio e seguro.
GLOSSARIO = {
    r'\b(?:VITDA|VITIDA|EBITIDA|EBTIDA|EBITA)\b': 'EBITDA',
    r'\bvekt?or\b': 'vetor',
    r'\bcres[cç][ãa]o\b': 'geração', r'\bcre[cç][ãa]o\b': 'geração',
    r'\bprofila[cç][ãa]o\b': 'perfil',
    r'\b(?:Shispei|Chispe|Xispe|Chispei)\b': 'XP',   # XP mal transcrita foneticamente
}

def limpa(txt):
    """Remove artefatos de captura: escapes literais, timestamps, <br>, hifenizacao quebrada."""
    if not txt:
        return ''
    t = txt.replace('\\n', ' ').replace('\r', ' ').replace('\n', ' ')
    t = re.sub(r'<br\s*/?>', ' ', t, flags=re.I)
    t = re.sub(r'\\?\[\d{1,2}:\d{2}(?::\d{2})?\\?\]', ' ', t)   # timestamps
    t = re.sub(r'(\w)-\s+(\w)', r'\1\2', t)                       # "TowerFor- ce" -> "TowerForce"
    return re.sub(r'\s+', ' ', t).strip()

def corrige_termos(txt, extra=None):
    for rx, sub in {**GLOSSARIO, **(extra or {})}.items():
        txt = re.sub(rx, sub, txt, flags=re.I)
    return txt

def _self_id(txt):
    for rx in _SELFID:
        m = rx.search(txt)
        if m and m.group(1).lower() not in _STOP:
            return m.group(1)
    return None

def _extrai_analista(txt):
    """De uma fala do operador, extrai (nome, banco) quando possivel (EN e PT)."""
    t = re.sub(r'\s+', ' ', txt)
    _N = r'([A-Z][\wçãáéíóâêõà]+(?:[ -][A-Z][\wçãáéíóâêõà]+){0,2})'
    _B = r'([A-ZÀ-Ú][\w&\.\- ]{1,28}?)'
    _Bl = r'([A-Za-zÀ-ú][\w&\.\- ]{1,28}?)'   # banco tolerante a minuscula ("banco safra")
    # PT: "pergunta vem do Lucas Lag, XP Investimentos" / "vem da Luisa Musse, banco safra"
    m = re.search(r'vem d[oaei]s?\s+' + _N + r'(?:\s*,\s*' + _Bl + r')?(?:[\.\,]|$)', t)
    if not m:
        # EN: "from Mr X from/by Bank"
        m = re.search(r'(?:from|de) (?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Sr\.?|Sra\.?)?\s*' + _N +
                      r'(?:[,\s]+(?:from|by|de|da|do)\s+' + _B + r')?(?:[\.\,]|$)', t)
    if not m:
        return None, None
    nome = (m.group(1) or '').strip()
    banco = (m.group(2) or '').strip() if m.lastindex and m.group(2) else None
    if banco:
        banco = re.sub(r'\s+(please|the floor|you may|your|good|para|com|obrigad|por gentileza).*$', '', banco, flags=re.I).strip(' .,')
        banco = re.sub(r'^banco\s+', '', banco, flags=re.I)      # "banco safra" -> "safra"
        banco = ' '.join(w if w.isupper() else w.capitalize() for w in banco.split())  # title-case
    return (nome or None), (banco or None)

def _sentencas(segments, glossario=None):
    """Junta os segmentos (conserta frase quebrada no meio), limpa/corrige e re-quebra em FRASES.
    Trabalhar por frase e' essencial: o Whisper corta frases no meio dos chunks."""
    txt = ' '.join(limpa(s) for s in segments if s and s.strip())
    txt = corrige_termos(txt, glossario)
    txt = re.sub(r'\s+', ' ', txt).strip()
    # nao quebrar frase em abreviacoes (Mr. Mrs. Dr. etc.) nem em iniciais
    txt = re.sub(r'\b(Mr|Mrs|Ms|Dr|Sr|Sra|St|vs|Inc|Ltd|Co|Jr|no|No)\.', r'\1<DOT>', txt)
    partes = re.split(r'(?<=[.?!])\s+', txt)
    return [p.strip().replace('<DOT>', '.') for p in partes if p.strip()]

def to_speaker_text(segments, lang='pt', glossario=None):
    """segments: lista de strings (texto por segmento do whisper, em ordem).
    Retorna markdown com turnos rotulados, sem timestamps."""
    segments = _sentencas(segments, glossario)   # agora cada item e' uma FRASE inteira
    turnos = []
    estado = 'apresentacao'  # apresentacao | operador | pos_intro | analista | executivo
    analista_atual = None
    exec_atual = None
    ana_seg = 0              # nº de segmentos ja' ditos pelo analista no turno atual
    OPENERS = ('let me go', 'let me start', 'let me take', 'let me address', 'let me answer')

    def _exec_cumprimenta(txt):
        """executivo abrindo a resposta cumprimentando o analista pelo 1o nome, ou opener classico."""
        if not (analista_atual and analista_atual[0]):
            return False
        first = re.escape(analista_atual[0].split()[0])
        n2 = _norm(txt)
        if re.match(r'^(hi|hello|hey|ola|ok|okay|so ok|thank you)?[, ]*' + _norm(first) + r'\b', n2):
            return True
        return any(n2.startswith(o) for o in OPENERS)
    rot_apres = '🗣️ Prepared remarks (company)' if lang == 'en' else '🗣️ Apresentação (companhia)'

    def push(rotulo, txt):
        if turnos and turnos[-1][0] == rotulo:
            turnos[-1][1].append(txt)
        else:
            turnos.append((rotulo, [txt]))

    def rot_analista():
        if analista_atual and analista_atual[0]:
            nome, banco = analista_atual
            return f'❓ {nome}' + (f' ({banco})' if banco else '')
        return '❓ Analista'

    for raw in segments:
        txt = re.sub(r'\s+', ' ', (raw or '').strip())
        if not txt:
            continue
        n = _norm(txt)

        if any(c in n for c in OPERADOR_CUES):
            eh_pergunta = any(c in n for c in QUESTION_CUES)
            # hand-off entre executivos durante a apresentacao NAO inicia Q&A
            if estado == 'apresentacao' and not eh_pergunta:
                push('🎙️ Operador', txt)
                continue
            nome, banco = _extrai_analista(txt)
            if nome:
                analista_atual = (nome, banco)
            push('🎙️ Operador', txt)
            estado = 'pos_intro' if nome else 'operador'
            continue

        nome_exec = _self_id(txt)
        virou_exec = bool(nome_exec) or any(_norm(p) in n for p in EXEC_START)

        if estado == 'apresentacao':
            # na apresentacao, uma auto-ID so troca o rotulo do bloco de prepared remarks
            push(rot_apres, txt); continue

        if estado in ('operador', 'pos_intro'):
            if virou_exec:
                exec_atual = nome_exec or exec_atual
                estado = 'executivo'
                push('💬 ' + (exec_atual or 'Executivo'), txt)
            else:
                estado = 'analista'; ana_seg = 0
                push(rot_analista(), txt)
            continue

        if estado == 'analista':
            if virou_exec or (ana_seg >= 1 and _exec_cumprimenta(txt)):
                exec_atual = nome_exec or exec_atual
                estado = 'executivo'
                push('💬 ' + (exec_atual or 'Executivo'), txt)
            else:
                ana_seg += 1
                push(rot_analista(), txt)
            continue

        if estado == 'executivo':
            if nome_exec:
                exec_atual = nome_exec
            push('💬 ' + (exec_atual or 'Executivo'), txt)
            continue

    linhas = []
    for rotulo, textos in turnos:
        corpo = re.sub(r'\s+', ' ', ' '.join(textos)).strip()
        linhas.append(f'**{rotulo}:** {corpo}')
    return '\n\n'.join(linhas)


if __name__ == '__main__':
    import sys
    data = open(sys.argv[1]).read()
    segs = re.split(r'\\?\[\d{1,2}:\d{2}(?::\d{2})?\\?\]', data)
    segs = [s.strip() for s in segs if s.strip()]
    if len(segs) < 3:
        segs = [l for l in data.splitlines() if l.strip()]
    print(to_speaker_text(segs, lang=sys.argv[2] if len(sys.argv) > 2 else 'en'))
