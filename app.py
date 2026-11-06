"""Maravilha Gestão | aplicação web local para pequenos comércios.

Execução de produção: python run.py  (Waitress + rede local controlada)
Bootstrap de administrador: python -m flask --app app create-admin
"""
from __future__ import annotations

import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

import click
from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from database import connect, initialize
from services import (BusinessError, create_client, create_delivery, create_sale,
                      positive_cents_to_brl, register_payment,
                      update_delivery_status, update_order_status)

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo('America/Sao_Paulo')
STATUSES = {
    'pendente': 'Pendente', 'em_preparacao': 'Em preparação', 'pronta': 'Pronta',
    'concluida': 'Concluída', 'cancelada': 'Cancelada', 'em_rota': 'Em rota',
    'entregue': 'Entregue', 'aberta': 'Aberta',
}


def now_local_date():
    return datetime.now(TZ).date().isoformat()


def _permanent_secret(instance: Path) -> str:
    from_env = os.environ.get('APP_SECRET', '').strip()
    if from_env:
        if len(from_env) < 32:
            raise RuntimeError('APP_SECRET deve possuir ao menos 32 caracteres aleatórios.')
        return from_env
    path = instance / '.session_secret'
    if path.exists():
        return path.read_text(encoding='utf-8').strip()
    token = secrets.token_urlsafe(48)
    path.write_text(token, encoding='utf-8')
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return token


def create_app(test_config=None):
    app = Flask(__name__, instance_path=str(ROOT / 'instance'))
    Path(app.instance_path).mkdir(exist_ok=True)
    app.config.update(
        SECRET_KEY=_permanent_secret(Path(app.instance_path)),
        DATABASE=os.environ.get('DB_PATH', str(Path(app.instance_path) / 'maravilha.db')),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '0') == '1',
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
        MAX_CONTENT_LENGTH=256 * 1024,
        TEMPLATES_AUTO_RELOAD=os.environ.get('APP_ENV') == 'development',
    )
    if test_config:
        app.config.update(test_config)
    initialize(app.config['DATABASE'])

    def db():
        if 'db' not in g:
            g.db = connect(app.config['DATABASE'])
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        conn = g.pop('db', None)
        if conn is not None:
            conn.close()

    @app.before_request
    def load_identity():
        g.user = None
        if session.get('user_id'):
            g.user = db().execute('''SELECT id, username, display_name, role, active
                 FROM users WHERE id=?''', (session['user_id'],)).fetchone()
            if g.user is None or not g.user['active']:
                session.clear()
                g.user = None
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            supplied = request.form.get('_csrf', '')
            expected = session.get('_csrf', '')
            if not supplied or not expected or not hmac.compare_digest(supplied, expected):
                abort(400, description='Formulário expirado. Atualize a página e tente novamente.')

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; font-src 'self'; object-src 'none'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        response.headers['Cache-Control'] = 'no-store'
        return response

    def csrf_token():
        if '_csrf' not in session:
            session['_csrf'] = secrets.token_urlsafe(32)
        return session['_csrf']

    def date_br(value):
        if not value:
            return 'Não informado'
        try:
            return datetime.fromisoformat(str(value)[:19]).strftime('%d/%m/%Y')
        except ValueError:
            return str(value)

    app.template_filter('date_br')(date_br)

    @app.context_processor
    def template_values():
        return dict(csrf_token=csrf_token, user=g.get('user'),
                    brl=positive_cents_to_brl, date_br=date_br,
                    status_label=lambda x: STATUSES.get(x, x), today=now_local_date)

    def login_required(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if g.user is None:
                flash('Entre na sua conta para continuar.', 'warning')
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapper

    def admin_required(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if g.user['role'] != 'admin':
                abort(403)
            return view(*args, **kwargs)
        return wrapper

    @app.route('/')
    def index():
        return redirect(url_for('dashboard' if g.user else 'login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if g.user:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username', '').strip().lower()[:80]
            password = request.form.get('password', '')
            row = db().execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            moment = datetime.now(TZ)
            locked = False
            if row and row['locked_until']:
                try:
                    locked = datetime.fromisoformat(row['locked_until']) > moment
                except ValueError:
                    locked = False
            if row and row['active'] and not locked and check_password_hash(row['password_hash'], password):
                db().execute('UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=?', (row['id'],))
                session.clear()
                session.permanent = True
                session['user_id'] = row['id']
                session['_csrf'] = secrets.token_urlsafe(32)
                flash('Bem-vindo(a), ' + row['display_name'].split()[0] + '!', 'success')
                return redirect(url_for('dashboard'))
            # Mensagem uniforme para evitar revelar se o usuário existe.
            if row and row['active'] and not locked:
                failures = row['failed_attempts'] + 1
                until = (moment + timedelta(minutes=15)).isoformat() if failures >= 5 else None
                db().execute('UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?',
                             (failures, until, row['id']))
            flash('Não foi possível entrar. Confira as credenciais ou tente novamente mais tarde.', 'danger')
        return render_template('login.html', title='Entrar')

    @app.post('/logout')
    @login_required
    def logout():
        session.clear()
        flash('Sessão encerrada com segurança.', 'info')
        return redirect(url_for('login'))

    @app.get('/dashboard')
    @login_required
    def dashboard():
        metrics = db().execute('''SELECT
           (SELECT COUNT(*) FROM sales WHERE status != 'cancelada') AS sales_count,
           (SELECT COALESCE(SUM(amount_cents),0) FROM sales WHERE status != 'cancelada') AS total_sold,
           (SELECT COALESCE(SUM(amount_cents),0) FROM payments) AS total_received,
           (SELECT COUNT(*) FROM orders WHERE status NOT IN ('concluida','cancelada')) AS open_orders,
           (SELECT COUNT(*) FROM deliveries WHERE status != 'entregue') AS open_deliveries''').fetchone()
        recent = db().execute('''SELECT s.*, c.name AS client_name,
                (SELECT COALESCE(SUM(p.amount_cents),0) FROM payments p WHERE p.sale_id=s.id) AS paid,
                o.status AS order_status
                FROM sales s LEFT JOIN clients c ON c.id=s.client_id
                LEFT JOIN orders o ON o.sale_id=s.id ORDER BY s.id DESC LIMIT 6''').fetchall()
        upcoming = db().execute('''SELECT o.*, s.description, c.name AS client_name
                FROM orders o JOIN sales s ON o.sale_id=s.id
                LEFT JOIN clients c ON s.client_id=c.id
                WHERE o.status NOT IN ('concluida','cancelada')
                ORDER BY o.expected_date, o.id LIMIT 5''').fetchall()
        return render_template('dashboard.html', title='Visão geral', metrics=metrics,
                               recent=recent, upcoming=upcoming)

    @app.route('/clientes', methods=['GET', 'POST'])
    @login_required
    def clients():
        if request.method == 'POST':
            try:
                client_id = create_client(db(), request.form.get('name', ''), request.form.get('phone'))
                flash(f'Cliente #{client_id} cadastrado com sucesso.', 'success')
                return redirect(url_for('clients'))
            except BusinessError as exc:
                flash(str(exc), 'danger')
        rows = db().execute('SELECT * FROM clients ORDER BY id DESC LIMIT 100').fetchall()
        return render_template('clients.html', title='Clientes', clients=rows)

    @app.get('/vendas')
    @login_required
    def sales():
        rows = db().execute('''SELECT s.*, c.name AS client_name,
           (SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE sale_id=s.id) AS paid
           FROM sales s LEFT JOIN clients c ON c.id=s.client_id ORDER BY s.id DESC LIMIT 100''').fetchall()
        return render_template('sales.html', title='Vendas', sales=rows)

    @app.route('/vendas/nova', methods=['GET', 'POST'])
    @login_required
    def sale_new():
        clients_rows = db().execute('SELECT id, name FROM clients ORDER BY name LIMIT 500').fetchall()
        if request.method == 'POST':
            try:
                client_id = request.form.get('client_id') or None
                has_order = request.form.get('has_order') == '1'
                sale_id = create_sale(
                    db(), client_id=client_id,
                    description=request.form.get('description', ''),
                    amount=request.form.get('amount', ''),
                    sale_date=request.form.get('sale_date', ''),
                    created_by=g.user['id'], has_order=has_order,
                    expected_date=request.form.get('expected_date'),
                    notes=request.form.get('notes', ''),
                    delivery_address=request.form.get('delivery_address', '')
                )
                flash('Venda registrada com sucesso.', 'success')
                return redirect(url_for('sale_detail', sale_id=sale_id, criado=1))
            except (BusinessError, ValueError) as exc:
                flash(str(exc), 'danger')
                return render_template('sale_new.html', title='Nova venda', clients=clients_rows,
                                       form=request.form), 400
        return render_template('sale_new.html', title='Nova venda', clients=clients_rows, form={})

    @app.get('/vendas/<int:sale_id>')
    @login_required
    def sale_detail(sale_id):
        sale = db().execute('''SELECT s.*, c.name AS client_name, c.phone AS client_phone
                   FROM sales s LEFT JOIN clients c ON c.id=s.client_id WHERE s.id=?''',
                   (sale_id,)).fetchone()
        if not sale:
            abort(404)
        payments = db().execute('SELECT * FROM payments WHERE sale_id=? ORDER BY id DESC', (sale_id,)).fetchall()
        paid = sum(p['amount_cents'] for p in payments)
        order = db().execute('SELECT * FROM orders WHERE sale_id=?', (sale_id,)).fetchone()
        delivery = db().execute('SELECT * FROM deliveries WHERE order_id=?', (order['id'],)).fetchone() if order else None
        return render_template('sale_detail.html', title=f'Venda #{sale_id:04d}', sale=sale,
                               payments=payments, paid=paid, remaining=max(0, sale['amount_cents']-paid),
                               order=order, delivery=delivery)

    @app.post('/vendas/<int:sale_id>/pagamentos')
    @login_required
    def payment_new(sale_id):
        try:
            register_payment(db(), sale_id=sale_id, amount=request.form.get('amount', ''),
                             method=request.form.get('method', ''),
                             received_on=request.form.get('received_on', ''),
                             created_by=g.user['id'])
            flash('Pagamento registrado e saldo atualizado.', 'success')
        except BusinessError as exc:
            flash(str(exc), 'danger')
        return redirect(url_for('sale_detail', sale_id=sale_id))

    @app.get('/encomendas')
    @login_required
    def orders():
        rows = db().execute('''SELECT o.*, s.description, s.amount_cents,
            c.name AS client_name, d.id AS delivery_id, d.status AS delivery_status
            FROM orders o JOIN sales s ON s.id=o.sale_id
            LEFT JOIN clients c ON c.id=s.client_id
            LEFT JOIN deliveries d ON d.order_id=o.id
            ORDER BY CASE WHEN o.status IN ('concluida','cancelada') THEN 1 ELSE 0 END,
                     o.expected_date, o.id DESC LIMIT 100''').fetchall()
        return render_template('orders.html', title='Encomendas', orders=rows)

    @app.post('/encomendas/<int:order_id>/situacao')
    @login_required
    def order_status(order_id):
        try:
            update_order_status(db(), order_id, request.form.get('status', ''))
            flash('Situação da encomenda atualizada.', 'success')
        except BusinessError as exc:
            flash(str(exc), 'danger')
        return redirect(url_for('orders'))

    @app.post('/encomendas/<int:order_id>/entrega')
    @login_required
    def delivery_create(order_id):
        try:
            create_delivery(db(), order_id, request.form.get('address', ''))
            flash('Entrega cadastrada.', 'success')
        except BusinessError as exc:
            flash(str(exc), 'danger')
        return redirect(url_for('orders'))

    @app.get('/entregas')
    @login_required
    def deliveries():
        rows = db().execute('''SELECT d.*, o.expected_date, s.description,
            c.name AS client_name, s.id AS sale_id
            FROM deliveries d JOIN orders o ON o.id=d.order_id
            JOIN sales s ON s.id=o.sale_id LEFT JOIN clients c ON c.id=s.client_id
            ORDER BY CASE WHEN d.status='entregue' THEN 1 ELSE 0 END, o.expected_date LIMIT 100''').fetchall()
        return render_template('deliveries.html', title='Entregas', deliveries=rows)

    @app.post('/entregas/<int:delivery_id>/situacao')
    @login_required
    def delivery_status(delivery_id):
        try:
            update_delivery_status(db(), delivery_id, request.form.get('status', ''), now_local_date())
            flash('Situação da entrega atualizada.', 'success')
        except BusinessError as exc:
            flash(str(exc), 'danger')
        return redirect(url_for('deliveries'))

    @app.route('/usuarios', methods=['GET', 'POST'])
    @admin_required
    def users():
        if request.method == 'POST':
            name = request.form.get('display_name', '').strip()
            username = request.form.get('username', '').strip().lower()
            password = request.form.get('password', '')
            role = request.form.get('role', '')
            if not (2 <= len(name) <= 100 and re.fullmatch('[a-z0-9._-]{3,30}', username)
                    and len(password) >= 12 and role in {'admin', 'funcionario'}):
                flash('Confira os campos. Usuário: 3 a 30 caracteres; senha: pelo menos 12.', 'danger')
            else:
                try:
                    db().execute('''INSERT INTO users (username,display_name,password_hash,role)
                        VALUES (?,?,?,?)''', (username, name, generate_password_hash(password, method='scrypt'), role))
                    flash('Acesso criado com sucesso.', 'success')
                    return redirect(url_for('users'))
                except sqlite3.IntegrityError:
                    flash('Já existe uma conta com este nome de usuário.', 'danger')
        rows = db().execute('SELECT id, username, display_name, role, active FROM users ORDER BY id').fetchall()
        return render_template('users.html', title='Equipe e acessos', users=rows)

    @app.post('/usuarios/<int:user_id>/alternar')
    @admin_required
    def user_toggle(user_id):
        if user_id == g.user['id']:
            flash('Você não pode desativar sua própria conta.', 'danger')
        else:
            row = db().execute('SELECT id, active FROM users WHERE id=?', (user_id,)).fetchone()
            if row:
                db().execute('UPDATE users SET active=? WHERE id=?', (0 if row['active'] else 1, user_id))
                flash('Permissão de acesso atualizada.', 'success')
        return redirect(url_for('users'))

    @app.route('/perfil/senha', methods=['GET', 'POST'])
    @login_required
    def password_change():
        if request.method == 'POST':
            current = request.form.get('current', '')
            new = request.form.get('new', '')
            confirm = request.form.get('confirm', '')
            row = db().execute('SELECT password_hash FROM users WHERE id=?', (g.user['id'],)).fetchone()
            if not check_password_hash(row['password_hash'], current):
                flash('Senha atual incorreta.', 'danger')
            elif len(new) < 12 or new != confirm:
                flash('A nova senha precisa ter 12 caracteres e coincidir com a confirmação.', 'danger')
            else:
                db().execute('UPDATE users SET password_hash=? WHERE id=?',
                             (generate_password_hash(new, method='scrypt'), g.user['id']))
                session.clear()
                flash('Senha atualizada. Entre novamente.', 'success')
                return redirect(url_for('login'))
        return render_template('password_change.html', title='Alterar senha')

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(500)
    def error_page(error):
        code = getattr(error, 'code', 500)
        descriptions = {400: 'Não foi possível processar o formulário.',
                        403: 'Você não tem permissão para acessar esta página.',
                        404: 'Este registro ou endereço não foi encontrado.',
                        500: 'Ocorreu um erro. Tente novamente ou procure o administrador.'}
        return render_template('error.html', title=f'Erro {code}', code=code,
                               message=descriptions.get(code, 'Erro inesperado.')), code

    @app.cli.command('create-admin')
    @click.option('--username', prompt='Nome de usuário (ex.: admin)', type=str)
    @click.option('--name', prompt='Nome exibido', type=str)
    @click.password_option('--password', confirmation_prompt=True)
    def create_admin(username, name, password):
        """Cria a primeira conta administradora, sem senhas padrão."""
        username = username.strip().lower()
        if not re.fullmatch('[a-z0-9._-]{3,30}', username) or len(password) < 12:
            raise click.ClickException('Usuário inválido ou senha com menos de 12 caracteres.')
        try:
            db().execute('''INSERT INTO users (username,display_name,password_hash,role)
                VALUES (?,?,?,?)''', (username, name.strip(), generate_password_hash(password, method='scrypt'), 'admin'))
        except sqlite3.IntegrityError as exc:
            raise click.ClickException('Esse nome de usuário já existe.') from exc
        click.echo('Administrador criado. Entre pelo navegador.')

    return app


app = create_app()

if __name__ == '__main__':
    # Somente para desenvolvimento local. Use run.py (Waitress) para operar na loja.
    app.run(host='127.0.0.1', port=8080, debug=False)
