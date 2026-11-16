"""Ponto de entrada para servidores WSGI (gunicorn, waitress)."""
from autofarma import create_app

app = create_app()
