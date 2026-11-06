"""Verifica a sintaxe dos templates Jinja sem executar o servidor."""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

root = Path(__file__).resolve().parents[1]
env = Environment(loader=FileSystemLoader(root/'templates'))
env.filters['date_br'] = lambda x: x
for path in sorted((root/'templates').glob('*.html')):
    env.get_template(path.name)
    print('OK', path.name)
