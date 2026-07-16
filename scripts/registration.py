#!/usr/bin/env python3
"""Registro genérico em formulários de webcast (Zoom, MZiQ, etc.)."""
import time

def try_register(page, name, email, company):
    """Preenche nome/sobrenome/email/empresa e envia. Retorna log das ações."""
    log = []
    first, last = (name.split(' ', 1) + [''])[:2]
    fields = [
        (['input[name*=first i]', 'input[id*=first i]', 'input[placeholder*=first i]', '#first_name'], first, 'first_name'),
        (['input[name*=last i]', 'input[id*=last i]', 'input[placeholder*=last i]', '#last_name'], last, 'last_name'),
        (['input[type=email]', 'input[name*=email i]', 'input[id*=email i]', 'input[placeholder*=mail i]'], email, 'email'),
        (['input[name*=company i]', 'input[name*=empresa i]', 'input[id*=org i]', 'input[placeholder*=empresa i]',
          'input[placeholder*=company i]', 'input[name*=custom i]'], company, 'company'),
        # fallback nome completo (formulários de campo único)
        (['input[name=name]', 'input[id=name]', 'input[placeholder*=nome i]', 'input[aria-label*=name i]'], name, 'full_name'),
    ]
    for sels, val, tag in fields:
        if not val: continue
        for s in sels:
            try:
                el = page.locator(s).first
                if el.is_visible(timeout=1200) and not el.input_value(timeout=800):
                    el.fill(val); log.append(f'fill:{tag}'); break
            except Exception:
                pass
    for s in ['button[type=submit]', 'button:has-text("Register")', 'button:has-text("Registrar")',
              'button:has-text("Inscrever")', 'button:has-text("Join")', 'button:has-text("Entrar")',
              'button:has-text("Acessar")', 'button:has-text("Assistir")', 'input[type=submit]']:
        try:
            el = page.locator(s).first
            if el.is_visible(timeout=1200):
                el.click(); log.append(f'click:{s}'); time.sleep(4); return log
        except Exception:
            pass
    log.append('submit:NAO_ENCONTRADO')
    return log
