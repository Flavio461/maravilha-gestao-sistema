"""Gera prévias HTML das 3 telas, usando os templates do projeto e dados fictícios.

As prévias não alteram o banco; servem para inspeção visual e capturas.
Requer Jinja2 (instalado com Flask).
"""
import argparse
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services import positive_cents_to_brl


def day_br(value):
    if not value:
        return 'Não informado'
    return datetime.fromisoformat(str(value)[:10]).strftime('%d/%m/%Y')


ROUTES = {
    'dashboard': 'tela1_menu.html', 'sale_new': 'tela2_nova_venda.html',
    'sale_detail': 'tela3_resultado.html', 'sales': 'tela1_menu.html',
    'clients': 'tela1_menu.html', 'orders': 'tela3_resultado.html',
    'deliveries': 'tela3_resultado.html', 'logout': 'tela1_menu.html',
    'users': 'tela1_menu.html', 'login': 'tela1_menu.html',
    'payment_new': 'tela3_resultado.html', 'password_change': 'tela1_menu.html'
}


def url_for(endpoint, **kwargs):
    if endpoint == 'static':
        return '../static/' + kwargs['filename']
    return ROUTES.get(endpoint, 'tela1_menu.html')


def render(db_path: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT/'templates'), autoescape=select_autoescape(['html']))
    env.filters['date_br'] = day_br
    env.globals.update(url_for=url_for, csrf_token=lambda: 'EXEMPLO_SEM_AUTENTICACAO',
                       get_flashed_messages=lambda **kwargs: [],
                       brl=positive_cents_to_brl, date_br=day_br,
                       status_label=lambda value: {
                           'pendente':'Pendente','em_preparacao':'Em preparação','pronta':'Pronta',
                           'concluida':'Concluída','cancelada':'Cancelada','em_rota':'Em rota',
                           'entregue':'Entregue','aberta':'Aberta'}.get(value, value),
                       today=lambda: str(date.today()))
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    user = dict(conn.execute('SELECT id, username, display_name, role FROM users LIMIT 1').fetchone())
    metrics = dict(conn.execute('''SELECT
      (SELECT COUNT(*) FROM sales WHERE status != 'cancelada') AS sales_count,
      (SELECT COALESCE(SUM(amount_cents),0) FROM sales WHERE status != 'cancelada') AS total_sold,
      (SELECT COALESCE(SUM(amount_cents),0) FROM payments) AS total_received,
      (SELECT COUNT(*) FROM orders WHERE status NOT IN ('concluida','cancelada')) AS open_orders,
      (SELECT COUNT(*) FROM deliveries WHERE status!='entregue') AS open_deliveries''').fetchone())
    recent = conn.execute('''SELECT s.*, c.name AS client_name,
                (SELECT COALESCE(SUM(p.amount_cents),0) FROM payments p WHERE p.sale_id=s.id) AS paid,
                o.status AS order_status FROM sales s LEFT JOIN clients c ON c.id=s.client_id
                LEFT JOIN orders o ON o.sale_id=s.id ORDER BY s.id DESC LIMIT 6''').fetchall()
    upcoming = conn.execute('''SELECT o.*, s.description, c.name AS client_name
                FROM orders o JOIN sales s ON o.sale_id=s.id
                LEFT JOIN clients c ON s.client_id=c.id
                WHERE o.status NOT IN ('concluida','cancelada')
                ORDER BY o.expected_date, o.id LIMIT 5''').fetchall()
    clients = conn.execute('SELECT id,name FROM clients ORDER BY name').fetchall()
    sale = conn.execute('''SELECT s.*, c.name AS client_name, c.phone AS client_phone
                  FROM sales s LEFT JOIN clients c ON c.id=s.client_id WHERE s.id=1''').fetchone()
    payments = conn.execute('SELECT * FROM payments WHERE sale_id=1').fetchall()
    order = conn.execute('SELECT * FROM orders WHERE sale_id=1').fetchone()
    delivery = conn.execute('SELECT * FROM deliveries WHERE order_id=?', (order['id'],)).fetchone()
    paid = sum(p['amount_cents'] for p in payments)
    examples = [
        ('dashboard.html', 'tela1_menu.html', 'dashboard', 'Visão geral',
         dict(metrics=metrics, recent=recent, upcoming=upcoming), {}),
        ('sale_new.html', 'tela2_nova_venda.html', 'sale_new', 'Nova venda',
         dict(clients=clients, form={
             'client_id':'1', 'description':'10 sacos de cimento CP II', 'amount':'420,00',
             'sale_date':str(date.today()), 'has_order':'1',
             'expected_date':str(date.today().fromordinal(date.today().toordinal()+2)),
             'delivery_address':'Rua das Acácias, 120, Centro',
             'notes':'Entrega no período da manhã.'
         }), {}),
        ('sale_detail.html', 'tela3_resultado.html', 'sale_detail', 'Venda #0001',
         dict(sale=sale, payments=payments, paid=paid,
              remaining=sale['amount_cents']-paid, order=order, delivery=delivery),
         {'criado':'1'})
    ]
    for template, filename, endpoint, title, ctx, args in examples:
        content = env.get_template(template).render(
            title=title, user=user, request=SimpleNamespace(endpoint=endpoint, args=args), **ctx)
        (out_dir/filename).write_text(content, encoding='utf-8')
        print('Prévia criada:', out_dir/filename)
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', default=str(ROOT/'instance'/'somente_demonstracao.db'))
    parser.add_argument('--output', default=str(ROOT/'previews'))
    opts = parser.parse_args()
    render(Path(opts.database), Path(opts.output))
