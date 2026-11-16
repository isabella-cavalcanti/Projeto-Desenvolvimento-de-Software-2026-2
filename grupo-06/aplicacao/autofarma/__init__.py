"""AutoFarma: gestão autônoma de linha de produção farmacêutica com
intervenção humana.

Camadas:
    apresentação  -> templates/ e static/
    aplicação     -> rotas.py, rotas_cadastros.py (web) e api.py (REST)
    negócio       -> servicos/
    integração    -> api.py (entrada das leituras) e agendador.py (temporizador)
    dados         -> models.py (SQLAlchemy; SQLite ou PostgreSQL)

Configuração por variáveis de ambiente (ver README):
    AUTOFARMA_SECRET        chave da sessão (obrigatória fora do modo demonstração)
    AUTOFARMA_API_CHAVE     chave exigida pela API de leituras
    AUTOFARMA_BANCO         URL do banco (padrão: SQLite em instance/autofarma.db)
    AUTOFARMA_DEMO          "1" carrega o cenário de demonstração e liga o simulador
    AUTOFARMA_ADMIN_SENHA   senha do primeiro administrador (fora do modo demonstração)
    AUTOFARMA_HTTPS         "1" quando servido por HTTPS: o cookie de sessão só trafega cifrado
"""
import os
import secrets
from datetime import timedelta

from flask import Flask

from .models import Usuario, db


def create_app(config=None):
    app = Flask(__name__)
    demo = os.environ.get("AUTOFARMA_DEMO", "1") == "1"
    app.config.update(
        SECRET_KEY=os.environ.get("AUTOFARMA_SECRET") or ("chave-apenas-para-demonstracao" if demo
                                                          else secrets.token_hex(32)),
        SQLALCHEMY_DATABASE_URI=os.environ.get("AUTOFARMA_BANCO", "sqlite:///autofarma.db"),
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=15),  # RNF01
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("AUTOFARMA_HTTPS") == "1",
        MAX_CONTENT_LENGTH=1024 * 1024,  # nenhum formulário ou leitura passa de 1 MB
        API_CHAVE=os.environ.get("AUTOFARMA_API_CHAVE") or ("chave-demo" if demo else None),
        DEMO=demo,
        CSRF_ATIVO=True,
        AGENDADOR=True,
        INTERVALO_ROTINAS=30,  # segundos
    )
    app.config.update(config or {})
    db.init_app(app)

    from .formato import numero
    app.jinja_env.filters["numero"] = numero

    from .api import api
    from .rotas import web
    from .rotas_cadastros import cadastros
    app.register_blueprint(web)
    app.register_blueprint(cadastros)
    app.register_blueprint(api, url_prefix="/api")

    with app.app_context():
        db.create_all()
        if Usuario.query.count() == 0:
            from . import seed
            if app.config["DEMO"]:
                seed.popular()
            else:
                seed.primeiro_administrador(os.environ.get("AUTOFARMA_ADMIN_SENHA"))

    if app.config["AGENDADOR"] and not app.config.get("TESTING"):
        from .agendador import iniciar
        iniciar(app)
    return app
