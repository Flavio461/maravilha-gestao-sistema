"""Testes ponta a ponta, executados quando Flask/Werkzeug estiverem instalados."""
import re
import sys
from pathlib import Path

import pytest
pytest.importorskip('flask')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from werkzeug.security import generate_password_hash
from database import connect


@pytest.fixture
def client(tmp_path):
    dbfile = tmp_path/'web.db'
    app = create_app({'TESTING':True, 'DATABASE':str(dbfile), 'SECRET_KEY':'test-not-production'})
    with connect(dbfile) as conn:
        conn.execute('INSERT INTO users (username,display_name,password_hash,role) VALUES (?,?,?,?)',
                     ('admin','Conta Teste',generate_password_hash('senha-apenas-para-testes-123',method='scrypt'),'admin'))
    yield app.test_client()


def token(html):
    match = re.search(r'name="_csrf" value="([^\"]+)"', html)
    assert match, 'Formulário precisa conter token CSRF'
    return match.group(1)


def login(client):
    t = token(client.get('/login').text)
    response = client.post('/login', data={'_csrf':t,'username':'admin',
                           'password':'senha-apenas-para-testes-123'})
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/dashboard')


def test_private_pages_redirect_to_login(client):
    res=client.get('/dashboard')
    assert res.status_code==302
    assert '/login' in res.headers['Location']


def test_authentication_and_pages(client):
    login(client)
    for route in ['/dashboard','/vendas','/vendas/nova','/clientes','/encomendas','/entregas','/usuarios']:
        res=client.get(route)
        assert res.status_code==200,(route,res.status_code)
        assert '<html' in res.text


def test_csrf_rejects_unprotected_post(client):
    login(client)
    res=client.post('/clientes',data={'name':'Cliente Teste'})
    assert res.status_code==400


def test_full_business_flow(client):
    login(client)
    t=token(client.get('/clientes').text)
    res=client.post('/clientes',data={'_csrf':t,'name':'Cliente Fictício','phone':''})
    assert res.status_code==302
    t=token(client.get('/vendas/nova').text)
    res=client.post('/vendas/nova',data={
        '_csrf':t,'client_id':'1','description':'10 sacos de cimento',
        'amount':'420,00','sale_date':'2026-11-03','has_order':'1',
        'expected_date':'2026-11-05','delivery_address':'Rua Modelo, 123','notes':'Teste'})
    assert res.status_code==302
    assert '/vendas/1' in res.headers['Location']
    res=client.get('/vendas/1')
    assert res.status_code==200
    assert '420,00' in res.text
    t=token(res.text)
    res=client.post('/vendas/1/pagamentos',data={'_csrf':t,'amount':'200,00','received_on':'2026-11-03','method':'pix'})
    assert res.status_code==302
    assert '220,00' in client.get('/vendas/1').text
    assert 'Cliente Fictício' in client.get('/encomendas').text
    assert 'Rua Modelo' in client.get('/entregas').text


def test_xss_escaped_in_page(client):
    login(client)
    t=token(client.get('/clientes').text)
    payload='<script>alert(1)</script> Cliente'
    client.post('/clientes',data={'_csrf':t,'name':payload,'phone':''})
    res=client.get('/clientes').text
    assert '&lt;script&gt;' in res
    assert payload not in res
