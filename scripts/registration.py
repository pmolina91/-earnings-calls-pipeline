#!/usr/bin/env python3
"""Registro em formulários de webcast. Adapter específico Zoom + fallback genérico."""
import time, os

def is_zoom_form(page):
    try:
        return page.locator('#question_first_name').first.is_visible(timeout=3000)
    except Exception:
        return False

def register_zoom(page, name, email, company, phone='', title_category='Buy side'):
    """Formulário de registro de webinar Zoom (padrão RIs BR via MZ Group)."""
    log = []
    first, last = (name.split(' ', 1) + [''])[:2]
    def fill(sel, val, tag):
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2500): el.fill(val); log.append(f'fill:{tag}')
        except Exception as e: log.append(f'ERRO:{tag}')
    fill('#question_first_name', first, 'first')
    fill('#question_last_name', last, 'last')
    fill('#question_email', email, 'email')
    if phone: fill('#question_Phone', phone, 'phone')
    fill('#question_Company', company, 'company')
    # categoria (checkboxes "Title"): JS-click no input correto + verificação
    try:
        ordem = ['Sell side','Buy side','Investor','Student','Journalist','Individual','Others']
        idx = ordem.index(title_category) if title_category in ordem else 1
        checked = page.evaluate('''(idx) => {
            const cbs = [...document.querySelectorAll('input[type=checkbox]')].filter(e => (e.name||'').startsWith('question_Title'));
            if (!cbs[idx]) return null;
            if (!cbs[idx].checked) cbs[idx].click();
            return cbs[idx].checked;
        }''', idx)
        log.append(f'categoria:{title_category}:{checked}')
    except Exception as e:
        log.append(f'ERRO:categoria:{e}')
    # consentimento LGPD (Lei 13.709/2018) — autorizado pelo usuário em 16/07/2026
    try:
        checked = page.evaluate('''() => {
            const cbs = [...document.querySelectorAll('input[type=checkbox]')];
            let el = cbs.find(e => (e.name||'').includes('13.709') || (e.name||'').toLowerCase().includes('compliance') || (e.name||'').includes('Law'));
            if (!el) el = cbs[cbs.length - 1];
            if (!el) return null;
            if (!el.checked) el.click();
            if (!el.checked) { // custom component: tentar o wrapper
                (el.closest('label') || el.parentElement).click();
            }
            return el.checked;
        }''')
        log.append(f'lgpd:{checked}')
    except Exception as e:
        log.append(f'ERRO:lgpd:{e}')
    time.sleep(1)
    # enviar
    try:
        page.locator('button:has-text("Inscrição"), button:has-text("Register"), button:has-text("Inscrever")').first.click(timeout=4000)
        log.append('submit'); time.sleep(5)
    except Exception:
        log.append('ERRO:submit')
    return log

def try_register(page, name, email, company, phone='', title_category='Buy side'):
    if is_zoom_form(page):
        return ['adapter:zoom'] + register_zoom(page, name, email, company, phone, title_category)
    # fallback genérico
    log = ['adapter:generico']
    first, last = (name.split(' ', 1) + [''])[:2]
    fields = [
        (['input[name*=first i]', 'input[id*=first i]', 'input[placeholder*=first i]'], first, 'first_name'),
        (['input[name*=last i]', 'input[id*=last i]', 'input[placeholder*=last i]'], last, 'last_name'),
        (['input[type=email]', 'input[name*=email i]', 'input[id*=email i]', 'input[placeholder*=mail i]'], email, 'email'),
        (['input[name*=phone i]', 'input[id*=phone i]', 'input[type=tel]'], phone, 'phone'),
        (['input[name*=company i]', 'input[name*=empresa i]', 'input[id*=org i]', 'input[placeholder*=empresa i]', 'input[placeholder*=company i]'], company, 'company'),
        (['input[name=name]', 'input[id=name]', 'input[placeholder*=nome i]'], name, 'full_name'),
    ]
    for sels, val, tag in fields:
        if not val: continue
        for s in sels:
            try:
                el = page.locator(s).first
                if el.is_visible(timeout=1200) and not el.input_value(timeout=800):
                    el.fill(val); log.append(f'fill:{tag}'); break
            except Exception: pass
    for s in ['button[type=submit]', 'button:has-text("Inscrição")', 'button:has-text("Register")', 'button:has-text("Registrar")',
              'button:has-text("Inscrever")', 'button:has-text("Join")', 'button:has-text("Entrar")', 'button:has-text("Acessar")',
              'button:has-text("Assistir")', 'input[type=submit]']:
        try:
            el = page.locator(s).first
            if el.is_visible(timeout=1200): el.click(); log.append(f'click:{s}'); time.sleep(4); return log
        except Exception: pass
    log.append('submit:NAO_ENCONTRADO')
    return log
