import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import connect, initialize
from inventory import create_product, move_stock
from services import BusinessError, create_client, create_sale


@pytest.fixture
def stock_db(tmp_path):
    path = tmp_path / 'stock.db'
    initialize(path)
    conn = connect(path)
    conn.execute("""INSERT INTO users (username, display_name, password_hash, role)
                    VALUES ('teste', 'Teste', 'hash', 'admin')""")
    yield conn, path
    conn.close()


def sell(conn, items, **options):
    args = dict(client_id=None, description='valor adulterado', amount='0,01',
                sale_date='2026-11-08', created_by=1, items=items)
    args.update(options)
    return create_sale(conn, **args)


def test_opening_stock_and_manual_movements_have_history(stock_db):
    conn, _ = stock_db
    product = create_product(conn, ' Cimento 50 kg ', '42,00', '10', 1)
    move_stock(conn, product, 'entrada', '5', 'Recebimento do fornecedor', 1)
    move_stock(conn, product, 'saida', '2', 'Sacos danificados', 1)
    row = conn.execute('SELECT * FROM products WHERE id=?', (product,)).fetchone()
    assert (row['name'], row['price_cents'], row['stock_quantity']) == ('Cimento 50 kg', 4200, 13)
    assert [m[0] for m in conn.execute(
        'SELECT quantity_delta FROM stock_movements ORDER BY id')] == [10, 5, -2]


@pytest.mark.parametrize('quantity', ['0', '-1', '1.5', '1,5', 'abc', '9' * 5000])
def test_invalid_quantities_do_not_change_stock(stock_db, quantity):
    conn, _ = stock_db
    product = create_product(conn, 'Tubo PVC', '12,50', '5', 1)
    with pytest.raises(BusinessError):
        move_stock(conn, product, 'entrada', quantity, 'Recebimento', 1)
    assert conn.execute('SELECT stock_quantity FROM products').fetchone()[0] == 5
    assert conn.execute('SELECT COUNT(*) FROM stock_movements').fetchone()[0] == 1


def test_duplicate_product_does_not_add_stock(stock_db):
    conn, _ = stock_db
    create_product(conn, 'Cimento', '42,00', '10', 1)
    with pytest.raises(BusinessError, match='Já existe'):
        create_product(conn, 'cimento', '42,00', '5', 1)
    assert conn.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 1
    assert conn.execute('SELECT SUM(quantity_delta) FROM stock_movements').fetchone()[0] == 10


def test_manual_withdrawal_cannot_exceed_available_stock(stock_db):
    conn, _ = stock_db
    product = create_product(conn, 'Tubo PVC', '12,50', '5', 1)
    with pytest.raises(BusinessError, match='maior que o estoque'):
        move_stock(conn, product, 'saida', '6', 'Correção da contagem', 1)
    assert conn.execute('SELECT stock_quantity FROM products').fetchone()[0] == 5
    assert conn.execute('SELECT COUNT(*) FROM stock_movements').fetchone()[0] == 1


def test_sale_uses_registered_prices_and_keeps_item_snapshots(stock_db):
    conn, _ = stock_db
    cement = create_product(conn, 'Cimento', '42,00', '10', 1)
    tube = create_product(conn, 'Tubo PVC', '12,50', '20', 1)
    sale = sell(conn, [(str(cement), '2'), (str(cement), '1'), (str(tube), '2')])
    assert conn.execute('SELECT amount_cents FROM sales WHERE id=?', (sale,)).fetchone()[0] == 15100
    assert [r[0] for r in conn.execute('SELECT stock_quantity FROM products ORDER BY id')] == [7, 18]
    conn.execute("UPDATE products SET name='Novo nome', price_cents=999 WHERE id=?", (cement,))
    item = conn.execute('SELECT * FROM sale_items WHERE sale_id=? AND product_id=?', (sale, cement)).fetchone()
    assert (item['product_name'], item['unit_price_cents'], item['quantity']) == ('Cimento', 4200, 3)


def test_insufficient_stock_rejects_entire_sale(stock_db):
    conn, _ = stock_db
    cement = create_product(conn, 'Cimento', '42,00', '10', 1)
    tube = create_product(conn, 'Tubo PVC', '12,50', '1', 1)
    with pytest.raises(BusinessError, match='disponíveis'):
        sell(conn, [(str(cement), '2'), (str(tube), '2')])
    assert conn.execute('SELECT COUNT(*) FROM sales').fetchone()[0] == 0
    assert [r[0] for r in conn.execute('SELECT stock_quantity FROM products ORDER BY id')] == [10, 1]


def test_delivery_failure_rolls_back_sale_items_and_stock(stock_db):
    conn, _ = stock_db
    client = create_client(conn, 'Cliente Teste')
    product = create_product(conn, 'Cimento', '42,00', '10', 1)
    with pytest.raises(sqlite3.IntegrityError):
        sell(conn, [(str(product), '2')], client_id=client, has_order=True,
             expected_date='2026-11-09', delivery_address='ab')
    assert conn.execute('SELECT COUNT(*) FROM sales').fetchone()[0] == 0
    assert conn.execute('SELECT COUNT(*) FROM sale_items').fetchone()[0] == 0
    assert conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0] == 0
    assert conn.execute('SELECT stock_quantity FROM products').fetchone()[0] == 10
    assert conn.execute('SELECT COUNT(*) FROM stock_movements').fetchone()[0] == 1


def test_parallel_sales_cannot_oversell(stock_db):
    conn, path = stock_db
    product = create_product(conn, 'Cimento', '42,00', '3', 1)

    def attempt_sale():
        worker = connect(path)
        try:
            sell(worker, [(str(product), '2')])
            return 'sold'
        except BusinessError:
            return 'rejected'
        finally:
            worker.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt_sale(), range(2)))
    assert sorted(results) == ['rejected', 'sold']
    assert conn.execute('SELECT stock_quantity FROM products').fetchone()[0] == 1
    assert conn.execute('SELECT COUNT(*) FROM sales').fetchone()[0] == 1


def test_initialization_adds_inventory_to_existing_database(tmp_path):
    path = tmp_path / 'existing.db'
    with sqlite3.connect(path) as old:
        old.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY);
            CREATE TABLE clients (id INTEGER PRIMARY KEY);
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY, client_id INTEGER, description TEXT,
                amount_cents INTEGER, sale_date TEXT, status TEXT, created_by INTEGER,
                created_at TEXT
            );
            INSERT INTO sales VALUES (7, NULL, 'Venda anterior', 4200,
                '2026-11-06', 'aberta', NULL, '2026-11-06');
        """)
    initialize(path)
    initialize(path)
    conn = connect(path)
    try:
        assert conn.execute('SELECT description FROM sales WHERE id=7').fetchone()[0] == 'Venda anterior'
        assert conn.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM sale_items').fetchone()[0] == 0
    finally:
        conn.close()
