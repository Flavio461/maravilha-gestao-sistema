"""Preenche SOMENTE um banco separado com dados inteiramente fictícios.

Não usar sobre banco real. Gera uma senha aleatória e não inclui credenciais no ZIP.
"""
import argparse
import hashlib
import os
import secrets
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from database import initialize, connect
from services import create_client, create_sale, register_payment


def hash_demo_password(password: str) -> str:
    # Formato compatível com generate_password_hash(method='scrypt') do Werkzeug.
    salt = secrets.token_hex(12)
    hashed = hashlib.scrypt(password.encode(), salt=salt.encode(), n=32768, r=8, p=1, maxmem=134217728).hex()
    return f'scrypt:32768:8:1${salt}${hashed}'


def seed(db_path: Path):
    if db_path.exists():
        raise SystemExit(f'Banco já existe: {db_path}. Não será sobrescrito.')
    initialize(db_path)
    password = secrets.token_urlsafe(18)
    with connect(db_path) as conn:
        conn.execute('INSERT INTO users(username,display_name,password_hash,role) VALUES (?,?,?,?)',
                     ('demo', 'Funcionário Demo', hash_demo_password(password), 'admin'))
        today = date.today()
        names = ['Cliente Exemplo', 'Obra Modelo', 'Pessoa Fictícia', 'Cliente Teste', 'Cliente Ilustrativo']
        ids = [create_client(conn, name) for name in names]
        sales_info = [
            (0, '10 sacos de cimento CP II', '420,00', 0, True, 2, 'Rua das Acácias, 120, Centro'),
            (1, '15 tijolos cerâmicos e 2 sacos de argamassa', '185,50', 1, False, 0, ''),
            (2, '5 sacos de areia média', '275,00', 1, True, 3, ''),
            (3, '6 tubos PVC 40 mm', '319,90', 2, True, 4, 'Avenida Central, 45'),
            (4, '1 lata de tinta branca 18L', '235,00', 2, False, 0, ''),
            (1, '2 latas de verniz e 3 pincéis', '132,00', 3, True, 7, ''),
            (0, '4 sacos de cimento e 1 impermeabilizante', '219,90', 3, False, 0, ''),
            (2, '3 sacos de cal e 2 sacos de massa', '168,00', 4, True, 8, ''),
        ]
        for idx, (client, item, amount, days_ago, has_order, days_ahead, address) in enumerate(sales_info):
            sid = create_sale(conn, client_id=ids[client], description=item, amount=amount,
                              sale_date=str(today-timedelta(days=days_ago)), created_by=1,
                              has_order=has_order,
                              expected_date=str(today+timedelta(days=days_ahead)) if has_order else None,
                              notes='Dados fictícios para demonstração.' if has_order else '', delivery_address=address)
            if idx == 0:
                register_payment(conn, sale_id=sid, amount='200,00', method='pix',
                                 received_on=str(today), created_by=1)
            elif idx in (1, 4, 5):
                register_payment(conn, sale_id=sid, amount=amount, method='dinheiro',
                                 received_on=str(today), created_by=1)
        conn.execute("UPDATE orders SET status='em_preparacao' WHERE sale_id=1")
        conn.execute("UPDATE orders SET status='pronta' WHERE sale_id=4")
    print('Banco DEMO criado:', db_path)
    print('Usuário: demo')
    print('Senha aleatória para DEMO:', password)
    return password


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', default=str(ROOT/'instance'/'somente_demonstracao.db'))
    args = parser.parse_args()
    seed(Path(args.database))
