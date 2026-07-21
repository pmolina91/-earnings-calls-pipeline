#!/usr/bin/env python3
"""Teste fim-a-fim do NOTION_TOKEN: search → acha database de Conferências → cria página de rascunho."""
import os, json, sys, requests
H = {'Authorization': f"Bearer {os.environ['NOTION_TOKEN']}",
     'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}
BASE='https://api.notion.com/v1'
out = {'ok': False}
try:
    # 1) quem sou eu
    me = requests.get(f'{BASE}/users/me', headers=H, timeout=30)
    out['users_me'] = me.status_code
    # 2) o que o token enxerga
    s = requests.post(f'{BASE}/search', headers=H, timeout=30,
                      json={'query': 'Confer', 'page_size': 20})
    s.raise_for_status()
    res = s.json().get('results', [])
    out['search_hits'] = len(res)
    out['sample'] = [{'id': r['id'], 'object': r['object'],
                      'title': (r.get('title') or [{}])[0].get('plain_text','') if r.get('title') else
                               ((r.get('properties',{}).get('Name',{}).get('title') or [{}])[0].get('plain_text','') if r['object']=='page' else '')}
                     for r in res[:10]]
    # 3) tenta achar um database "Conferências de Resultado" e criar página de teste
    db = next((r for r in res if r['object']=='database' and 'Confer' in json.dumps(r.get('title',''))), None)
    if db:
        ticker_db = db['id']
        p = requests.post(f'{BASE}/pages', headers=H, timeout=30, json={
            'parent': {'database_id': ticker_db},
            'properties': {'Name': {'title':[{'text':{'content':'TESTE PIPELINE — pode apagar'}}]}}})
        out['create_status'] = p.status_code
        out['created_page'] = p.json().get('id') if p.ok else p.text[:300]
        out['ok'] = p.ok
    else:
        # sem database achado: cria página de teste sob a primeira página visível
        pg = next((r for r in res if r['object']=='page'), None)
        if pg:
            p = requests.post(f'{BASE}/pages', headers=H, timeout=30, json={
                'parent': {'page_id': pg['id']},
                'properties': {'title': {'title':[{'text':{'content':'TESTE PIPELINE — pode apagar'}}]}}})
            out['create_status'] = p.status_code
            out['created_page'] = p.json().get('id') if p.ok else p.text[:300]
            out['ok'] = p.ok
        else:
            out['erro'] = 'token nao enxerga nenhuma pagina/database — falta Connections na pagina-mae'
except Exception as e:
    out['erro'] = str(e)[:300]
os.makedirs('work', exist_ok=True)
json.dump(out, open('work/notion_test.json','w'), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))
sys.exit(0 if out.get('ok') or 'search_hits' in out else 1)
