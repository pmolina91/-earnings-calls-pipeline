#!/usr/bin/env python3
"""Cliente mínimo da API do Notion (token de integração interna via NOTION_TOKEN)."""
import os, re, requests
H = lambda: {'Authorization': f"Bearer {os.environ['NOTION_TOKEN']}",
             'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}
BASE='https://api.notion.com/v1'

def create_call_page(database_id, title, ano_trimestre, data_iso):
    # tolerante a esquema: consulta as propriedades reais do database e só envia as que existem
    props_reais = {}
    try:
        rq = requests.get(f'{BASE}/databases/{database_id}', headers=H(), timeout=30)
        rq.raise_for_status()
        props_reais = rq.json().get('properties', {})
    except Exception:
        pass
    payload = {}
    titulo_key = next((k for k, v in props_reais.items() if v.get('type') == 'title'), 'Name')
    payload[titulo_key] = {'title': [{'text': {'content': title}}]}
    def tem(nome, tipo):
        return nome in props_reais and props_reais[nome].get('type') == tipo
    if tem('Data', 'date'):
        payload['Data'] = {'date': {'start': data_iso}}
    if tem('Ano_Trimestre', 'rich_text'):
        payload['Ano_Trimestre'] = {'rich_text': [{'text': {'content': ano_trimestre}}]}
    # esquema alternativo (tabelas novas): Ano (number) + Trimestre (select)
    import re as _re
    m = _re.match(r'(\d)T(\d{2})', ano_trimestre or '')
    if m:
        if tem('Ano', 'number'):
            payload['Ano'] = {'number': 2000 + int(m.group(2))}
        if tem('Trimestre', 'select'):
            payload['Trimestre'] = {'select': {'name': f'{m.group(1)}T'}}
    r = requests.post(f'{BASE}/pages', headers=H(), json={
        'parent': {'database_id': database_id}, 'properties': payload})
    r.raise_for_status(); return r.json()['id']

def append_text(page_id, text, heading=None):
    blocks=[]
    if heading:
        blocks.append({'object':'block','type':'heading_3',
            'heading_3':{'rich_text':[{'text':{'content':heading}}]}})
    # Notion limita 2000 chars por rich_text
    for i in range(0, len(text), 1900):
        blocks.append({'object':'block','type':'paragraph',
            'paragraph':{'rich_text':[{'text':{'content':text[i:i+1900]}}]}})
    for i in range(0, len(blocks), 90):
        r = requests.patch(f'{BASE}/blocks/{page_id}/children', headers=H(),
                           json={'children': blocks[i:i+90]})
        r.raise_for_status()


def _plain(block):
    t = block.get('type')
    rt = (block.get(t) or {}).get('rich_text', []) if t else []
    return ''.join(x.get('plain_text', '') for x in rt)

def list_children(block_id):
    out, cursor = [], None
    while True:
        params = {'page_size': 100}
        if cursor: params['start_cursor'] = cursor
        r = requests.get(f'{BASE}/blocks/{block_id}/children', headers=H(), params=params, timeout=30)
        r.raise_for_status(); j = r.json()
        out += j.get('results', [])
        if not j.get('has_more'): break
        cursor = j.get('next_cursor')
    return out

def delete_block(block_id):
    try:
        requests.delete(f'{BASE}/blocks/{block_id}', headers=H(), timeout=30)
        return True
    except Exception:
        return False

_LIVE_MARKERS = ['transcrição (ao vivo)', 'transcricao (ao vivo)', 'transcrição ao vivo',
                 'transcricao ao vivo', 'transcrição automática', 'transcricao automatica',
                 'nova sessão de transcrição', 'nova sessao de transcricao']
_KEEP_MARKERS = ['📌', '🔁', '📋', '📊', 'resumo do call', 'q&a formatado',
                 'vs. call anterior', 'transcrição final', 'transcricao final']

def delete_live_blocks(page_id):
    """Apaga a transcricao AO VIVO (do primeiro marcador ao fim), preservando as secoes
    do cerebro (Resumo/Q&A) caso ja existam. Retorna nº de blocos apagados."""
    filhos = list_children(page_id)
    start = None
    for i, b in enumerate(filhos):
        low = _plain(b).lower()
        if any(mk in low for mk in _LIVE_MARKERS):
            start = i; break
    if start is None:
        return 0
    apagados = 0
    for b in filhos[start:]:
        low = _plain(b).lower()
        if any(mk in low for mk in _KEEP_MARKERS):
            break
        if delete_block(b['id']): apagados += 1
    return apagados

def append_markdown(page_id, md, heading=None):
    """Anexa markdown simples: cada paragrafo (\\n\\n) vira um bloco; **Rótulo:** vira bold no inicio."""
    blocks = []
    if heading:
        blocks.append({'object':'block','type':'heading_2',
            'heading_2':{'rich_text':[{'text':{'content':heading}}]}})
    for par in [p for p in md.split('\n\n') if p.strip()]:
        rich = []
        m = re.match(r'^\*\*(.+?):\*\*\s*(.*)$', par, re.S)
        resto = m.group(2) if m else par
        if m:
            rich.append({'type':'text','text':{'content':(m.group(1)+': ')[:1900]},
                         'annotations':{'bold':True}})
        for i in range(0, max(len(resto),1), 1900):
            rich.append({'type':'text','text':{'content':resto[i:i+1900]}})
        blocks.append({'object':'block','type':'paragraph','paragraph':{'rich_text':rich[:100]}})
    for i in range(0, len(blocks), 90):
        r = requests.patch(f'{BASE}/blocks/{page_id}/children', headers=H(),
                           json={'children': blocks[i:i+90]})
        r.raise_for_status()

def find_call_page(database_id, title_contains):
    """Procura pagina existente no database cujo titulo contenha o texto (regra: UMA pagina por call)."""
    r = requests.post(f'{BASE}/databases/{database_id}/query', headers=H(), json={
        'page_size': 20})
    r.raise_for_status()
    for res in r.json().get('results', []):
        props = res.get('properties', {})
        tit = next((v for v in props.values() if v.get('type') == 'title'), None)
        texto = ''.join(t.get('plain_text','') for t in (tit or {}).get('title', []))
        if title_contains.lower() in texto.lower() and not res.get('archived'):
            return res['id']
    return None

def find_or_create_call_page(database_id, title, ano_trimestre, data_iso, separador=None):
    """Regra do usuario (23/07): UMA pagina por call. Se existe, anexa separador e retorna; senao cria."""
    chave = f"Call {ano_trimestre} - " if ano_trimestre else title
    pid = find_call_page(database_id, chave)
    if pid:
        if separador:
            append_text(pid, separador, heading='—' * 3)
        return pid
    return create_call_page(database_id, title, ano_trimestre, data_iso)
