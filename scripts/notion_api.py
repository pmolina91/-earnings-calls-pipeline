#!/usr/bin/env python3
"""Cliente mínimo da API do Notion (token de integração interna via NOTION_TOKEN)."""
import os, requests
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
