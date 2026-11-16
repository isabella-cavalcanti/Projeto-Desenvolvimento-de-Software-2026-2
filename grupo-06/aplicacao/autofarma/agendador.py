"""Temporizador: executa as rotinas automáticas em segundo plano.

É o ator "Temporizador" do diagrama de casos de uso: escalona intervenções
sem resposta (RF10), bloqueia lotes vencidos (RF16) e retoma lotes que
aguardavam material (RF04).
"""
import threading
import time

_iniciado = False


def iniciar(app):
    global _iniciado
    if _iniciado:
        return
    _iniciado = True

    def laco():
        from .entrada import trava
        from .models import db
        from .servicos import producao
        while True:
            time.sleep(app.config["INTERVALO_ROTINAS"])
            with app.app_context():
                try:
                    with trava:
                        producao.rotinas_automaticas()
                except Exception:  # uma falha não pode derrubar o temporizador
                    db.session.rollback()
                    app.logger.exception("Falha nas rotinas automáticas")
                finally:
                    db.session.remove()

    threading.Thread(target=laco, name="autofarma-temporizador", daemon=True).start()
