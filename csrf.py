"""Geração e validação dos tokens CSRF dos formulários."""

import hmac
import secrets

from flask import abort, request, session


def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']


def protect_form():
    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return

    supplied = request.form.get('_csrf', '')
    expected = session.get('_csrf', '')
    if (
        not supplied
        or not expected
        or not supplied.isascii()
        or not hmac.compare_digest(supplied, expected)
    ):
        abort(400, description='Formulário expirado. Atualize a página e tente novamente.')
