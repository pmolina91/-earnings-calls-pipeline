#!/usr/bin/env python3
"""Cliente mínimo da API do Notion (token de integração interna via NOTION_TOKEN)."""
import os, requests
H = lambda: {'Authorization': f"Bearer {os.environ['NOTION_TOKEN']}",
             'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}
BASE='https://api.notion.com/v1'

def create_call_page(database_id, title, ano_trimestre, data_iso):
    r = requests.post(f'{BASE}/pages', headers=H(), json={
        'parent': {'database_id': database_id},
        'properties': {
            'Name': {'title':[{'text':{'content': title}}]},
            'Ano_Trimestre': {'rich_text':[{'text':{'content': ano_trimestre}}]},
            'Data': {'date': {'start': data_iso}},
        }})
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
