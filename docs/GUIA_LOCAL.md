# Guia de uso local

Depois de seguir a [instalação no README](../README.md#como-rodar), use este guia para cuidar dos dados da loja, abrir o sistema em outros aparelhos ou experimentar o projeto com dados fictícios.

## Banco de dados e backup

O banco SQLite fica em `instance/maravilha.db`. Para gerar uma cópia consistente, mesmo com o sistema em uso, execute na pasta do projeto:

- Windows: `.venv\Scripts\python.exe scripts\backup.py`
- Linux: `.venv/bin/python scripts/backup.py`

O arquivo vai para `backups/`. Guarde cópias em um local protegido, separado do computador principal. Para restaurar, desligue o sistema, guarde uma cópia do banco atual e substitua `instance/maravilha.db` pelo backup escolhido antes de reiniciar.

Mantenha bancos, backups e o arquivo `instance/.session_secret` fora do GitHub.

## Acesso por outros aparelhos da loja

Por padrão, só o computador que roda o sistema consegue acessá-lo. Para usar outros aparelhos da loja, mantenha o servidor em `127.0.0.1:8080` e use um proxy HTTPS na rede local. Não abra a porta 8080 para a internet.

Exemplo com Caddy. Substitua `192.168.1.50` pelo endereço fixo do computador da loja:

```caddyfile
192.168.1.50 {
    tls internal
    reverse_proxy 127.0.0.1:8080
}
```

Configure o proxy para aceitar conexões apenas da rede privada da loja. Com `tls internal`, cada aparelho precisa confiar no certificado raiz do Caddy. Antes de iniciar o sistema sob HTTPS, defina `COOKIE_SECURE=1` para que o cookie de sessão só seja enviado por HTTPS. Teste a configuração em cada aparelho antes de usar dados reais.

## Experimentar com dados fictícios

O script de demonstração cria um banco separado e mostra uma senha aleatória para o usuário `demo`. Ele não sobrescreve bancos existentes. Com as dependências instaladas, rode estes comandos no PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py --database instance/demo.db
$env:DB_PATH = 'instance/demo.db'
.\.venv\Scripts\python.exe run.py
```

No Linux:

```bash
.venv/bin/python scripts/seed_demo.py --database instance/demo.db
DB_PATH=instance/demo.db .venv/bin/python run.py
```

No Windows, feche esse terminal depois do teste para descartar a variável `DB_PATH` da sessão.

## Testes

Com o ambiente virtual ativo e as dependências do projeto instaladas:

```bash
python -m pip install pytest
python -m pytest -q
```

O GitHub Actions também roda os testes quando há um envio ou um pull request.
