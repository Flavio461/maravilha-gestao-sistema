"""Demonstração pública com banco separado e somente dados fictícios."""
from contextlib import closing
from datetime import date, timedelta
import os
from pathlib import Path
import secrets
import sqlite3

from database import connect, initialize
from inventory import create_product
from services import create_client, create_sale, register_payment
from werkzeug.security import generate_password_hash


def prepare_database(path):
    path = Path(path).resolve()
    if path.exists():
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
            marker = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='public_demo'"
            ).fetchone()
        if marker:
            return
        raise RuntimeError('A demonstração não pode usar um banco de dados existente da loja.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('demo-inicial-' + secrets.token_hex(8) + '.db')
    try:
        initialize(temporary)
        with closing(connect(temporary)) as conn:
            user_id = conn.execute(
                'INSERT INTO users (username,display_name,password_hash,role) VALUES (?,?,?,?)',
                ('demo', 'Visitante da demonstração',
                 generate_password_hash(secrets.token_urlsafe(32)), 'funcionario')
            ).lastrowid
            client_id = create_client(conn, 'Cliente de exemplo')
            create_client(conn, 'Cliente da reforma (exemplo)')
            cement = create_product(conn, 'Cimento 50 kg', '42,00', '40', user_id)
            mortar = create_product(conn, 'Argamassa 20 kg', '25,00', '50', user_id)
            create_product(conn, 'Tubo PVC 25 mm', '18,50', '25', user_id)
            today = date.today()
            sale_id = create_sale(
                conn, client_id=client_id, description='', amount='',
                sale_date=today.isoformat(), created_by=user_id,
                items=[(str(cement), '10'), (str(mortar), '5')], has_order=True,
                expected_date=(today + timedelta(days=2)).isoformat(),
                delivery_address='Rua de Exemplo, 123 (endereço fictício)',
                notes='Pedido fictício para conhecer o sistema.')
            register_payment(conn, sale_id=sale_id, amount='200,00', method='pix',
                             received_on=today.isoformat(), created_by=user_id)
            conn.execute('CREATE TABLE public_demo (version INTEGER NOT NULL)')
            conn.execute('INSERT INTO public_demo VALUES (1)')
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
        Path(str(temporary) + '-wal').unlink(missing_ok=True)
        Path(str(temporary) + '-shm').unlink(missing_ok=True)


def create_demo_app(path):
    prepare_database(path)
    from app import create_app
    from flask import abort, redirect, request, session, url_for
    app = create_app({'DATABASE': str(path), 'DEMO_MODE': True})

    @app.before_request
    def protect_demo_account():
        if request.endpoint == 'password_change':
            abort(403)

    @app.post('/demo')
    def enter_demo():
        with closing(connect(app.config['DATABASE'])) as conn:
            user = conn.execute(
                "SELECT id FROM users WHERE username='demo' AND role='funcionario' AND active=1"
            ).fetchone()
        if user is None:
            abort(503)
        session.clear()
        session.permanent = True
        session['user_id'] = user['id']
        session['_csrf'] = secrets.token_urlsafe(32)
        return redirect(url_for('dashboard'))

    @app.get('/healthz')
    def demo_health():
        try:
            uri = Path(app.config['DATABASE']).resolve().as_uri() + '?mode=ro'
            with closing(sqlite3.connect(uri, uri=True, timeout=2)) as conn:
                for table in ('users', 'products', 'sales'):
                    conn.execute('SELECT id FROM ' + table + ' LIMIT 1').fetchone()
            return {'status': 'UP', 'database': 'ok'}
        except sqlite3.Error:
            app.logger.exception('Falha na verificação de disponibilidade da demonstração.')
            return {'status': 'DOWN'}, 503
    return app


if __name__ == '__main__':
    from waitress import serve
    database_path = Path(__file__).resolve().parent / 'instance' / 'demo-publica.db'
    os.environ['DB_PATH'] = str(database_path)
    application = create_demo_app(database_path)
    serve(application, host='0.0.0.0', port=int(os.environ.get('PORT', '8080')), threads=4)
