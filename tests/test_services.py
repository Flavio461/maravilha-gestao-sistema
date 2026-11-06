import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import connect, initialize
from services import (BusinessError, create_client, create_delivery, create_sale,
                      money_to_cents, register_payment, update_delivery_status,
                      update_order_status)


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / 'test.db'
    initialize(path)
    c = connect(path)
    c.execute("INSERT INTO users(username,display_name,password_hash,role) VALUES ('test','Teste','hash','admin')")
    yield c
    c.close()


def create_example(conn, order=True, delivery=False):
    client = create_client(conn, 'Cliente Teste')
    sale = create_sale(conn, client_id=client, description='10 sacos de cimento', amount='420,00',
                       sale_date='2026-11-03', created_by=1, has_order=order,
                       expected_date='2026-11-05' if order else None,
                       delivery_address='Rua Modelo, 123' if delivery else '')
    return client, sale


def test_register_sale_order_and_delivery_transaction(conn):
    client, sale = create_example(conn, delivery=True)
    assert conn.execute('SELECT count(*) FROM sales').fetchone()[0] == 1
    assert conn.execute('SELECT count(*) FROM orders').fetchone()[0] == 1
    assert conn.execute('SELECT count(*) FROM deliveries').fetchone()[0] == 1
    assert conn.execute('SELECT amount_cents FROM sales WHERE id=?', (sale,)).fetchone()[0] == 42000


def test_partial_and_full_payment(conn):
    _, sale = create_example(conn)
    register_payment(conn, sale_id=sale, amount='200,00', method='pix', received_on='2026-11-03', created_by=1)
    assert conn.execute('SELECT status FROM sales WHERE id=?', (sale,)).fetchone()[0] == 'aberta'
    register_payment(conn, sale_id=sale, amount='220,00', method='dinheiro', received_on='2026-11-03', created_by=1)
    assert conn.execute('SELECT status FROM sales WHERE id=?', (sale,)).fetchone()[0] == 'concluida'
    with pytest.raises(BusinessError, match='saldo pendente'):
        register_payment(conn, sale_id=sale, amount='1', method='pix', received_on='2026-11-03', created_by=1)


def test_overpayment_is_rejected_without_inserting(conn):
    _, sale = create_example(conn)
    with pytest.raises(BusinessError, match='saldo pendente'):
        register_payment(conn, sale_id=sale, amount='500,00', method='pix', received_on='2026-11-03', created_by=1)
    assert conn.execute('SELECT count(*) FROM payments').fetchone()[0] == 0


def test_order_requires_client(conn):
    with pytest.raises(BusinessError, match='Selecione um cliente'):
        create_sale(conn, client_id=None, description='Cimento 10 sacos', amount='100,00',
                    sale_date='2026-11-03', created_by=1, has_order=True, expected_date='2026-11-05')
    assert conn.execute('SELECT count(*) FROM sales').fetchone()[0] == 0


def test_payment_requires_existing_sale(conn):
    with pytest.raises(BusinessError, match='não encontrada'):
        register_payment(conn, sale_id=999, amount='1,00', method='pix', received_on='2026-11-03', created_by=1)


def test_status_validations(conn):
    _, sale = create_example(conn, delivery=True)
    oid = conn.execute('SELECT id FROM orders WHERE sale_id=?', (sale,)).fetchone()[0]
    did = conn.execute('SELECT id FROM deliveries WHERE order_id=?', (oid,)).fetchone()[0]
    update_order_status(conn, oid, 'em_preparacao')
    with pytest.raises(BusinessError):
        update_order_status(conn, oid, 'inexistente')
    update_delivery_status(conn, did, 'entregue', '2026-11-05')
    assert conn.execute('SELECT delivered_on FROM deliveries WHERE id=?', (did,)).fetchone()[0] == '2026-11-05'
    with pytest.raises(BusinessError, match='não pode voltar'):
        update_delivery_status(conn, did, 'pendente', '2026-11-05')


def test_money_parsing_and_rejection():
    assert money_to_cents('1.234,56') == 123456
    assert money_to_cents('420,00') == 42000
    assert money_to_cents('420.00') == 42000
    for invalid in ['-1', '0', '0,00', '1,001', 'abc']:
        with pytest.raises(BusinessError):
            money_to_cents(invalid)


def test_duplicate_delivery_is_rejected(conn):
    _, sale = create_example(conn, delivery=True)
    oid = conn.execute('SELECT id FROM orders WHERE sale_id=?', (sale,)).fetchone()[0]
    with pytest.raises(BusinessError, match='já possui'):
        create_delivery(conn, oid, 'Rua Dupla, 123')


def test_sql_injection_like_text_is_stored_as_data(conn):
    cid = create_client(conn, "Cliente ' OR 1=1 --")
    assert conn.execute('SELECT name FROM clients WHERE id=?', (cid,)).fetchone()[0] == "Cliente ' OR 1=1 --"
    assert conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clients'").fetchone()


def test_foreign_keys_work(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO payments(sale_id,amount_cents,received_on,method) VALUES(999,100,'2026-11-03','pix')")
