# Arquitetura do MVP

**Parceiro:** Materiais de Construção Maravilha, Januária, MG.

**Problema:** registros desorganizados de vendas, pagamentos e encomendas, perda de informações e atrasos em pedidos e entregas.

**Usuários:** funcionários de atendimento e administração; clientes e responsáveis pelas entregas são beneficiários indiretos.

## Camadas

1. **Apresentação:** templates HTML com Jinja2, Bootstrap e `static/css/app.css`. Formulários com rótulos e validação do navegador.
2. **Aplicação e regras:** `app.py` oferece rotas e autenticação; `services.py` valida valores, datas, relações e saldos.
3. **Persistência:** `database.py` cria o esquema relacional SQLite e gerencia conexões; consultas SQL são parametrizadas.

## Entidades

- `users (id PK, username UNIQUE, display_name, password_hash, role, active, failed_attempts, locked_until)`: controla acesso individual.
- `clients (id PK, name, phone)`: identifica clientes em vendas e encomendas.
- `sales (id PK, client_id FK opcional, description, amount_cents, sale_date, status, created_by FK)`: registra operações.
- `payments (id PK, sale_id FK, amount_cents, received_on, method, created_by FK)`: pagamentos de cada venda.
- `orders (id PK, sale_id FK UNIQUE, expected_date, status, notes)`: uma encomenda por venda, quando aplicável.
- `deliveries (id PK, order_id FK UNIQUE, address, status, delivered_on)`: até uma entrega por encomenda.

## Regras e restrições

- Vendas precisam ter descrição, valor positivo e data válida.
- Encomendas exigem cliente identificado e data prevista não anterior à venda.
- Pagamentos positivos só são aceitos até o saldo da venda, após `BEGIN IMMEDIATE` para evitar sobrepagamentos simultâneos.
- Entregas precisam estar vinculadas a encomendas existentes; registro de conclusão exige data.
- Chaves estrangeiras, índices e regras `CHECK` são aplicados no SQLite.
- Valores financeiros são armazenados em centavos (`INTEGER`) para evitar arredondamentos binários.

## Principais requisitos

- RF01 Cadastro de clientes, RF02 Registro de vendas, RF03 Controle de pagamentos.
- RF04 Encomendas, RF05 Registro de entregas, RF06 Acompanhamento da entrega.
- RNF01 Autenticação, RNF02 consultas e saídas seguras, RNF03 funcionamento local e desempenho, RNF04 acessibilidade.

## Limites do projeto

Sem emissão de NF-e, integrações bancárias, aplicativo nativo, hospedagem em nuvem e estoque detalhado. Foco na utilidade para os funcionários da pequena loja.
