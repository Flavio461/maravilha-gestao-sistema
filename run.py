"""Inicialização com Waitress. Use proxy HTTPS para acesso por outros aparelhos."""
import os
from waitress import serve
from app import app


if __name__ == '__main__':
    host = os.environ.get('LISTEN_HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '8080'))
    if host not in {'127.0.0.1', 'localhost', '::1'} and os.environ.get('ALLOW_INSECURE_LAN') != '1':
        raise SystemExit('Para acessar outros aparelhos, use um proxy HTTPS na frente de 127.0.0.1:8080. Consulte README.md.')
    print(f'Maravilha Gestão: http://{host}:{port} (Ctrl+C para parar)')
    serve(app, host=host, port=port, threads=4)
