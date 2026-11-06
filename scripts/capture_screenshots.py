"""Captura as três telas a partir dos templates renderizados com dados fictícios.

As folhas de estilo locais são incorporadas para viabilizar a captura offline.
"""
import os
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PREVIEWS = ROOT/'previews'
OUT = ROOT/'docs'/'capturas'
OUT.mkdir(parents=True, exist_ok=True)

bootstrap = (ROOT/'static/css/bootstrap.min.css').read_text(encoding='utf-8')
style = (ROOT/'static/css/app.css').read_text(encoding='utf-8')

with sync_playwright() as p:
    executable = (os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
                  or shutil.which('chromium-browser') or shutil.which('google-chrome'))
    options = {'headless': True}
    if executable:
        options['executable_path'] = executable
    if os.name != 'nt' and hasattr(os, 'geteuid') and os.geteuid() == 0:
        options['args'] = ['--no-sandbox']
    browser = p.chromium.launch(**options)
    context = browser.new_context(viewport={'width':1440,'height':980}, device_scale_factor=1, locale='pt-BR', timezone_id='America/Sao_Paulo')
    page = context.new_page()
    for filename, output in [
        ('tela1_menu.html', 'tela1_menu.png'),
        ('tela2_nova_venda.html', 'tela2_nova_venda.png'),
        ('tela3_resultado.html', 'tela3_resultado.png')]:
        html = (PREVIEWS/filename).read_text(encoding='utf-8')
        html = html.replace('<link rel="stylesheet" href="../static/css/bootstrap.min.css">', f'<style>{bootstrap}</style>')
        html = html.replace('<link rel="stylesheet" href="../static/css/app.css">', f'<style>{style}</style>')
        html = html.replace('<script defer src="../static/js/app.js"></script>', '')
        page.set_content(html, wait_until='load')
        page.screenshot(path=str(OUT/output), full_page=True, animations='disabled')
        print(output, '| título:', page.title(), '| altura:', round(page.locator('body').bounding_box()['height']))
    browser.close()
