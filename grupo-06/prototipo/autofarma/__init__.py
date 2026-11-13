"""AutoFarma: gestão autônoma de linha de produção farmacêutica com
intervenção humana. Protótipo do Projeto Extensionista.

Camadas:
    apresentação  -> templates/ e rotas.py
    aplicação     -> rotas.py (web) e api.py (REST)
    negócio       -> servicos/
    dados         -> models.py (SQLAlchemy + SQLite)
"""
import os
from datetime import timedelta

from flask import Flask

from .models import Usuario, db


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("AUTOFARMA_SECRET", "troque-esta-chave-em-producao"),
        SQLALCHEMY_DATABASE_URI="sqlite:///autofarma.db",
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=15),  # RNF01
    )
    app.config.update(config or {})
    db.init_app(app)
    from .formato import numero
    app.jinja_env.filters["numero"] = numero

    from .api import api
    from .rotas import web
    app.register_blueprint(web)
    app.register_blueprint(api, url_prefix="/api")

    with app.app_context():
        db.create_all()
        if app.config.get("POPULAR", True) and Usuario.query.count() == 0:
            from .seed import popular
            popular()
    return app
