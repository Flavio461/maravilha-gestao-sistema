import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from demo import create_demo_app, prepare_database


def csrf(client):
    return re.search(r'name="_csrf" value="([^"]+)"', client.get('/login').text)[1]


def test_demo_login_and_operational_pages(tmp_path):
    application = create_demo_app(tmp_path / 'demo.db')
    application.config['TESTING'] = True
    client = application.test_client()
    assert client.post('/demo').status_code == 400
    assert client.post('/demo', data={'_csrf': csrf(client)}).status_code == 302
    for route in ['/dashboard', '/produtos', '/produtos/1', '/vendas/1', '/encomendas', '/entregas']:
        response = client.get(route)
        assert response.status_code == 200
        assert 'Demonstração pública' in response.text
    assert client.get('/usuarios').status_code == 403
    assert client.get('/perfil/senha').status_code == 403
    assert client.get('/healthz').json == {'status': 'UP', 'database': 'ok'}


def test_health_detects_missing_database_without_creating_it(tmp_path):
    application = create_demo_app(tmp_path / 'demo.db')
    missing = tmp_path / 'missing.db'
    application.config['DATABASE'] = str(missing)
    response = application.test_client().get('/healthz')
    assert response.status_code == 503
    assert response.json == {'status': 'DOWN'}
    assert not missing.exists()


def test_demo_seed_preserves_changes_on_restart(tmp_path):
    path = tmp_path / 'demo.db'
    prepare_database(path)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute('SELECT stock_quantity FROM products ORDER BY id').fetchall() == [(30,), (45,), (25,)]
        assert conn.execute('SELECT amount_cents FROM sales').fetchone()[0] == 54500
        conn.execute("INSERT INTO clients(name) VALUES ('Novo exemplo')")
        conn.commit()
    prepare_database(path)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute('SELECT COUNT(*) FROM clients').fetchone()[0] == 3
        assert conn.execute('SELECT COUNT(*) FROM sales').fetchone()[0] == 1


def test_demo_refuses_existing_store_database(tmp_path):
    path = tmp_path / 'store.db'
    create_app({'DATABASE': str(path), 'TESTING': True})
    with pytest.raises(RuntimeError, match='banco de dados existente da loja'):
        prepare_database(path)


def test_regular_app_has_no_demo_access(tmp_path):
    application = create_app({'DATABASE': str(tmp_path / 'store.db'), 'TESTING': True})
    client = application.test_client()
    assert 'Entrar na demonstração' not in client.get('/login').text
    assert client.get('/healthz').status_code == 404
    assert client.post('/demo', data={'_csrf': csrf(client)}).status_code == 404
    assert client.post('/login', data={'_csrf': 'inválido'}).status_code == 400
