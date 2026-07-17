#!/usr/bin/env python3
"""Inscrição no mailing de RI das empresas. Para cada empresa: abre o RI, acha o
link de mailing/cadastro/newsletter, preenche identidade (secrets), aceita LGPD
(autorizado pelo usuário), envia e verifica confirmação.
Saída por empresa: OK / CAPTCHA (manual) / FORM_NAO_ACHADO / ERRO."""
import json, sys, os, re, time, traceback
from playwright.sync_api import sync_playwright

spec = json.load(open(sys.argv[1]))
NAME, EMAIL = os.environ['REG_NAME'], os.environ['REG_EMAIL']
COMPANY, PHONE = os.environ['REG_COMPANY'], os.environ.get('REG_PHONE','')
out = {}

def achar_form_mailing(page):
    """Procura link para página de mailing e navega."""
    for pat in ['mailing', 'cadastr', 'newsletter', 'e-mail alert', 'email alert', 'alertas']:
        try:
            el = page.locator(f'a:has-text("{pat}")').first
            if el.is_visible(timeout=1500):
                el.click(); time.sleep(5); return True
        except Exception: pass
    # links por href
    try:
        href = page.evaluate('''() => { const a=[...document.querySelectorAll('a')].find(a=>/mailing|cadastro|newsletter|alert/i.test(a.href)); return a?a.href:null }''')
        if href: page.goto(href, timeout=45000); time.sleep(5); return True
    except Exception: pass
    return False

def preencher(page):
    log = []
    first, last = (NAME.split(' ',1)+[''])[:2]
    campos = [
        (['input[type=email]','input[name*=email i]','input[id*=email i]'], EMAIL, 'email'),
        (['input[name*=first i]','input[id*=first i]'], first, 'first'),
        (['input[name*=last i]','input[id*=last i]'], last, 'last'),
        (['input[name*=name i]:not([name*=last i]):not([name*=first i])','input[id*=nome i]','input[placeholder*=nome i]'], NAME, 'nome'),
        (['input[name*=company i]','input[name*=empresa i]','input[placeholder*=empresa i]'], COMPANY, 'empresa'),
        (['input[type=tel]','input[name*=phone i]','input[name*=telefone i]'], PHONE, 'tel'),
    ]
    for sels, val, tag in campos:
        if not val: continue
        for s in sels:
            try:
                el = page.locator(s).first
                if el.is_visible(timeout=1200) and not el.input_value(timeout=800):
                    el.fill(val); log.append(tag); break
            except Exception: pass
    # selects de perfil (investidor/analista)
    try:
        n = page.evaluate('''() => {
          let c=0; for (const s of document.querySelectorAll('select')) {
            for (const o of s.options) {
              if (/investidor|analista|analyst|investor|buy/i.test(o.text)) { s.value=o.value; s.dispatchEvent(new Event('change',{bubbles:true})); c++; break; } } }
          return c }''')
        if n: log.append(f'select:{n}')
    except Exception: pass
    # checkboxes de consentimento (LGPD/termos) — autorizado pelo usuário
    try:
        n = page.evaluate('''() => { let c=0; for (const cb of document.querySelectorAll('input[type=checkbox]')) { if (!cb.checked) { cb.click(); c++; } } return c }''')
        if n: log.append(f'checks:{n}')
    except Exception: pass
    return log

def tem_captcha(page):
    try:
        return page.evaluate('''() => !!document.querySelector('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], .g-recaptcha, .h-captcha, [class*="captcha" i]')''')
    except Exception:
        return False

def enviar(page):
    for s in ['button[type=submit]','input[type=submit]','button:has-text("Cadastrar")','button:has-text("Enviar")',
              'button:has-text("Inscrever")','button:has-text("Assinar")','button:has-text("Subscribe")','button:has-text("Register")']:
        try:
            el = page.locator(s).first
            if el.is_visible(timeout=1500): el.click(); time.sleep(5); return True
        except Exception: pass
    return False

with sync_playwright() as pw:
    browser = pw.chromium.launch(args=['--no-sandbox'])
    for emp in spec['empresas']:
        t = emp['ticker']
        try:
            page = browser.new_context(locale='pt-BR').new_page()
            page.goto(emp['url'], timeout=45000, wait_until='domcontentloaded'); time.sleep(6)
            # fechar banners de cookies (recusar/aceitar o que aparecer primeiro)
            for s in ['button:has-text("ACEITAR")','button:has-text("Aceitar")','button:has-text("Accept")','button:has-text("Concordo")','button:has-text("OK")']:
                try:
                    el = page.locator(s).first
                    if el.is_visible(timeout=1000): el.click(); break
                except Exception: pass
            achou = achar_form_mailing(page)
            if not achou and not page.locator('input[type=email]').first.is_visible(timeout=1500):
                out[t] = {'status': 'FORM_NAO_ACHADO', 'url': page.url[:100]}
                page.close(); continue
            if tem_captcha(page):
                out[t] = {'status': 'CAPTCHA', 'url': page.url[:100]}
                page.close(); continue
            log = preencher(page)
            ok_env = enviar(page)
            body = ''
            try: body = page.inner_text('body')[:2000].lower()
            except Exception: pass
            conf = any(k in body for k in ['sucesso','obrigado','confirma','cadastrado','recebemos','thank you','subscribed','verifique seu e-mail'])
            out[t] = {'status': 'OK' if (ok_env and conf) else ('ENVIADO_SEM_CONFIRMACAO' if ok_env else 'SUBMIT_NAO_ACHADO'),
                      'acoes': log, 'url': page.url[:100]}
            page.close()
        except Exception as e:
            out[t] = {'status': 'ERRO', 'msg': str(e)[:150]}
        print(t, out[t]['status'], flush=True)
    browser.close()
os.makedirs('work', exist_ok=True)
json.dump(out, open('work/mailing.json','w'), indent=1, ensure_ascii=False)
