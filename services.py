"""Regras de negócio independentes da interface Flask, testáveis com SQLite."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from sqlite3 import Connection, IntegrityError


class BusinessError(ValueError):
    """Entrada inválida ou operação não permitida."""


def text_required(value: str | None, label: str, min_length: int = 1, max_length: int = 300) -> str:
    cleaned = (value or '').strip()
    if not min_length <= len(cleaned) <= max_length:
        raise BusinessError(f'{label}: informe entre {min_length} e {max_length} caracteres.')
    return cleaned


def money_to_cents(value: str | int | float) -> int:
    raw = str(value).strip().replace('R$', '').replace(' ', '')
    if not raw:
        raise BusinessError('Informe o valor em reais.')
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    try:
        amount = Decimal(raw)
        if not amount.is_finite() or amount <= 0 or amount > Decimal('9999999.99'):
            raise ValueError()
        if amount.as_tuple().exponent < -2:
            raise ValueError()
        return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        raise BusinessError('Informe um valor válido, positivo, com até duas casas decimais.') from None


def positive_cents_to_brl(cents: int | None) -> str:
    x = int(cents or 0)
    sign = '-' if x < 0 else ''
    reais, centavos = divmod(abs(x), 100)
    return f'{sign}R$ {reais:,}'.replace(',', '.') + f',{centavos:02d}'


def valid_date(value: str | None, label: str = 'Data') -> str:
    try:
        date.fromisoformat(value or '')
    except ValueError:
        raise BusinessError(f'{label}: informe uma data válida.') from None
    return str(value)


def create_client(conn: Connection, name: str, phone: str | None = None) -> int:
    name = text_required(name, 'Nome', 2, 120)
    phone = (phone or '').strip()
    if len(phone) > 25:
        raise BusinessError('Telefone muito longo.')
    cursor = conn.execute('INSERT INTO clients (name, phone) VALUES (?,?)', (name, phone or None))
    return int(cursor.lastrowid)


def create_sale(conn: Connection, *, client_id: int | None, description: str,
                amount: str, sale_date: str, created_by: int | None,
                has_order: bool = False, expected_date: str | None = None,
                notes: str = '', delivery_address: str = '') -> int:
    description = text_required(description, 'Descrição dos materiais', 3, 600)
    amount_cents = money_to_cents(amount)
    sale_date = valid_date(sale_date, 'Data da venda')
    notes = (notes or '').strip()
    if len(notes) > 400:
        raise BusinessError('Observações excedem 400 caracteres.')
    try:
        client_id = int(client_id) if client_id not in (None, '', '0') else None
    except (TypeError, ValueError):
        raise BusinessError('Selecione um cliente válido.') from None
    if has_order:
        if client_id is None:
            raise BusinessError('Selecione um cliente para registrar uma encomenda.')
        expected_date = valid_date(expected_date, 'Data prevista da encomenda')
        if expected_date < sale_date:
            raise BusinessError('A data prevista não pode ser anterior à data da venda.')
    if client_id is not None and not conn.execute('SELECT 1 FROM clients WHERE id=?', (client_id,)).fetchone():
        raise BusinessError('O cliente selecionado não existe.')
    if delivery_address.strip() and not has_order:
        raise BusinessError('A entrega deve estar associada a uma encomenda.')
    if len(delivery_address) > 240:
        raise BusinessError('Endereço muito longo.')

    # Um único commit preserva a integridade entre venda, encomenda e entrega.
    conn.execute('BEGIN IMMEDIATE')
    try:
        cur = conn.execute('''INSERT INTO sales
            (client_id, description, amount_cents, sale_date, created_by)
            VALUES (?,?,?,?,?)''', (client_id, description, amount_cents, sale_date, created_by))
        sale_id = int(cur.lastrowid)
        if has_order:
            order = conn.execute('''INSERT INTO orders (sale_id, expected_date, notes)
                VALUES (?,?,?)''', (sale_id, expected_date, notes))
            if delivery_address.strip():
                conn.execute('INSERT INTO deliveries (order_id, address) VALUES (?,?)',
                             (order.lastrowid, delivery_address.strip()))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
    return sale_id


def register_payment(conn: Connection, *, sale_id: int, amount: str, method: str,
                     received_on: str, created_by: int | None) -> int:
    cents = money_to_cents(amount)
    if method not in {'pix', 'dinheiro', 'cartao', 'outro'}:
        raise BusinessError('Selecione uma forma de pagamento válida.')
    received_on = valid_date(received_on, 'Data do recebimento')
    conn.execute('BEGIN IMMEDIATE')
    try:
        row = conn.execute('''SELECT s.id, s.status, s.amount_cents,
            COALESCE(SUM(p.amount_cents),0) AS paid
            FROM sales s LEFT JOIN payments p ON s.id=p.sale_id
            WHERE s.id=? GROUP BY s.id''', (sale_id,)).fetchone()
        if not row:
            raise BusinessError('Venda não encontrada.')
        if row['status'] == 'cancelada':
            raise BusinessError('Não é possível registrar pagamento para uma venda cancelada.')
        if cents > row['amount_cents'] - row['paid']:
            raise BusinessError('O pagamento não pode superar o saldo pendente.')
        cur = conn.execute('''INSERT INTO payments (sale_id, amount_cents, received_on, method, created_by)
            VALUES (?,?,?,?,?)''', (sale_id, cents, received_on, method, created_by))
        if cents == row['amount_cents'] - row['paid']:
            conn.execute("UPDATE sales SET status='concluida' WHERE id=?", (sale_id,))
        conn.execute('COMMIT')
        return int(cur.lastrowid)
    except Exception:
        conn.execute('ROLLBACK')
        raise


def create_delivery(conn: Connection, order_id: int, address: str) -> int:
    address = text_required(address, 'Endereço da entrega', 5, 240)
    if not conn.execute('SELECT 1 FROM orders WHERE id=?', (order_id,)).fetchone():
        raise BusinessError('Encomenda não encontrada.')
    try:
        cur = conn.execute('INSERT INTO deliveries(order_id,address) VALUES (?,?)', (order_id, address))
        return int(cur.lastrowid)
    except IntegrityError:
        raise BusinessError('Esta encomenda já possui uma entrega cadastrada.') from None


def update_order_status(conn: Connection, order_id: int, status: str) -> None:
    valid = {'pendente', 'em_preparacao', 'pronta', 'concluida', 'cancelada'}
    if status not in valid:
        raise BusinessError('Situação da encomenda inválida.')
    row = conn.execute('SELECT status FROM orders WHERE id=?', (order_id,)).fetchone()
    if not row:
        raise BusinessError('Encomenda não encontrada.')
    if row['status'] in {'cancelada', 'concluida'} and status != row['status']:
        raise BusinessError('A encomenda finalizada não pode retornar a um estado anterior.')
    conn.execute('UPDATE orders SET status=? WHERE id=?', (status, order_id))


def update_delivery_status(conn: Connection, delivery_id: int, status: str, on: str) -> None:
    if status not in {'pendente', 'em_rota', 'entregue'}:
        raise BusinessError('Situação da entrega inválida.')
    row = conn.execute('SELECT status FROM deliveries WHERE id=?', (delivery_id,)).fetchone()
    if not row:
        raise BusinessError('Entrega não encontrada.')
    if row['status'] == 'entregue' and status != 'entregue':
        raise BusinessError('Uma entrega concluída não pode voltar para pendente.')
    delivered_on = valid_date(on) if status == 'entregue' else None
    conn.execute('UPDATE deliveries SET status=?, delivered_on=? WHERE id=?',
                 (status, delivered_on, delivery_id))
