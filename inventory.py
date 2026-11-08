"""Cadastro de produtos e movimentações do estoque disponível para venda."""
from sqlite3 import Connection, IntegrityError, SQLITE_CONSTRAINT_UNIQUE

from services import BusinessError, money_to_cents, text_required


def whole_quantity(value, minimum=1):
    raw = str(value).strip()
    if not raw.isascii() or not raw.isdecimal() or len(raw) > 7 or not minimum <= int(raw) <= 1000000:
        raise BusinessError(f'Informe uma quantidade inteira entre {minimum} e 1000000.')
    return int(raw)


def create_product(conn: Connection, name, price, opening_stock, created_by):
    name = text_required(name, 'Nome do produto', 2, 100)
    price_cents = money_to_cents(price)
    stock = whole_quantity(opening_stock, minimum=0)
    conn.execute('BEGIN IMMEDIATE')
    try:
        cursor = conn.execute(
            'INSERT INTO products (name, price_cents, stock_quantity) VALUES (?,?,?)',
            (name, price_cents, stock),
        )
        product_id = int(cursor.lastrowid)
        if stock:
            conn.execute('''INSERT INTO stock_movements
                (product_id, quantity_delta, reason, created_by) VALUES (?,?,?,?)''',
                (product_id, stock, 'Estoque inicial', created_by))
        conn.execute('COMMIT')
        return product_id
    except IntegrityError as exc:
        conn.execute('ROLLBACK')
        if exc.sqlite_errorcode == SQLITE_CONSTRAINT_UNIQUE:
            raise BusinessError('Já existe um produto com esse nome.') from None
        raise
    except Exception:
        conn.execute('ROLLBACK')
        raise


def move_stock(conn: Connection, product_id, movement, quantity, reason, created_by):
    if movement not in {'entrada', 'saida'}:
        raise BusinessError('Escolha entrada de mercadoria ou saída do estoque.')
    quantity = whole_quantity(quantity)
    reason = text_required(reason, 'Motivo da movimentação', 3, 240)
    delta = quantity if movement == 'entrada' else -quantity
    conn.execute('BEGIN IMMEDIATE')
    try:
        product = conn.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
        if not product:
            raise BusinessError('Produto não encontrado.')
        if product['stock_quantity'] + delta < 0:
            raise BusinessError('A saída é maior que o estoque disponível.')
        if product['stock_quantity'] + delta > 1000000:
            raise BusinessError('O estoque não pode ultrapassar 1000000 unidades.')
        conn.execute('UPDATE products SET stock_quantity=stock_quantity+? WHERE id=?',
                     (delta, product_id))
        conn.execute('''INSERT INTO stock_movements
            (product_id, quantity_delta, reason, created_by) VALUES (?,?,?,?)''',
            (product_id, delta, reason, created_by))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise


def prepare_sale_items(conn: Connection, items):
    if not items or len(items) > 20:
        raise BusinessError('Selecione de 1 a 20 produtos para a venda.')
    quantities = {}
    for product_id, quantity in items:
        product_id = whole_quantity(product_id)
        quantities[product_id] = quantities.get(product_id, 0) + whole_quantity(quantity)
    selected = []
    for product_id, quantity in quantities.items():
        product = conn.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
        if not product:
            raise BusinessError('Um dos produtos selecionados não existe.')
        if quantity > product['stock_quantity']:
            raise BusinessError(
                f"{product['name']}: há {product['stock_quantity']} unidade(s) disponíveis."
            )
        selected.append(dict(product, quantity=quantity))
    return selected


def record_sale_items(conn: Connection, sale_id, items, created_by):
    """Usa a mesma transação da venda, aberta em services.create_sale."""
    for item in items:
        conn.execute('''INSERT INTO sale_items
            (sale_id, product_id, product_name, quantity, unit_price_cents)
            VALUES (?,?,?,?,?)''',
            (sale_id, item['id'], item['name'], item['quantity'], item['price_cents']))
        conn.execute('UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?',
                     (item['quantity'], item['id']))
        conn.execute('''INSERT INTO stock_movements
            (product_id, quantity_delta, reason, sale_id, created_by) VALUES (?,?,?,?,?)''',
            (item['id'], -item['quantity'], f'Venda #{sale_id:04d}', sale_id, created_by))
