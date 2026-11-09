# Maravilha Gestão

Um sistema web para organizar a rotina da Materiais de Construção Maravilha, em Januária (MG). A ideia é reunir vendas, pagamentos, encomendas e entregas num só lugar, para a equipe saber o que já foi feito e o que ainda está pendente.

## O que dá para fazer

- Cadastrar clientes e registrar vendas.
- Cadastrar produtos, registrar entradas e saídas e consultar o estoque disponível.
- Vender produtos cadastrados com cálculo do total e baixa automática no estoque.
- Anotar pagamentos e conferir quanto falta receber em cada venda.
- Acompanhar encomendas e entregas.
- Gerenciar o acesso dos funcionários.

O sistema roda no próprio computador da loja. Foi feito com Python, Flask, SQLite e Bootstrap.

No painel inicial, siga os atalhos em **Por onde começar**. Em **Produtos e estoque**,
cadastre cada material com preço e quantidade inicial. Abra **Movimentar estoque**
para registrar recebimentos ou perdas. Em **Nova venda**, selecione um ou mais
produtos e informe as quantidades. Ao salvar, o sistema calcula o total e baixa
o estoque disponível. As quantidades são em unidades inteiras, como sacos, tubos
e latas. Vendas com descrição manual registram apenas o valor do atendimento.

## Como rodar

Você vai precisar do **Python 3.12 ou mais recente**. Baixe ou clone o repositório antes de seguir os passos.

**No Windows**, execute estes arquivos na ordem:

1. `setup_windows.bat` — instala as dependências.
2. `CRIAR_ADMIN.bat` — cria a primeira conta. Escolha uma senha de pelo menos 12 caracteres.
3. `INICIAR.bat` — abre o servidor local. Nas próximas vezes, basta executar este arquivo.

**No Linux**, abra um terminal na pasta do projeto:

```bash
bash setup_linux.sh
.venv/bin/python -m flask --app app create-admin
.venv/bin/python run.py
```

Com o servidor rodando, abra [localhost:8080](http://127.0.0.1:8080) no navegador do mesmo computador. O banco de dados é criado na primeira execução.

## Uma olhada no sistema

![Painel com vendas recentes, valores recebidos e próximas encomendas](docs/capturas/tela1_menu.png)

As telas usam dados fictícios. Veja também o [formulário de venda](docs/capturas/tela2_nova_venda.png) e o [resumo de uma venda](docs/capturas/tela3_resultado.png).

## Para consultar depois

A demonstração pública pode ser hospedada no Render pelo arquivo `render.yaml`,
ou como Web Service com build `pip install -r requirements.txt` e início
`python demo.py`. Na configuração manual, selecione a branch `feat/demo-publica`,
o plano Free, a variável `COOKIE_SECURE=1` e o Health Check Path `/healthz`.
O botão da tela inicial abre uma conta de demonstração sem acesso à administração.
O banco `instance/demo-publica.db` contém apenas exemplos e fica separado dos dados
da loja. No Render gratuito, ele pode ser recriado após suspensão ou reinício do
serviço. Essa hospedagem serve para demonstração e avaliação.

O endereço `/healthz` verifica a leitura das tabelas de usuários, produtos e vendas.
Responde `200` e `UP` quando disponível, ou `503` e `DOWN` quando o banco falha.
Configure esse caminho no Render e acompanhe eventos e logs no painel do serviço.
A existência do endpoint, sozinha, não configura um monitor externo nem representa
um histórico de disponibilidade.

- [Guia de uso local](docs/GUIA_LOCAL.md): backups, acesso por outros aparelhos, demonstração e testes.
- [Arquitetura e modelo de dados](docs/ARQUITETURA_E_MODELO.md): como o sistema funciona por dentro.
- [Componentes de terceiros](THIRD_PARTY_NOTICES.md): créditos e licença do Bootstrap.
