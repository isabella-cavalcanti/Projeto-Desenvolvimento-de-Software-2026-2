"""API REST (RNF09): porta de entrada das leituras da linha.

Quem chama é o sistema supervisório da fábrica (ou o simulador.py, que faz
o papel dele). Toda chamada exige a chave no cabeçalho X-API-Key (RNF01).
"""
import hmac
import math
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session

from .entrada import trava
from .models import Lote, ParametroControle, StatusLote, db
from .servicos import producao
from .servicos.auditoria import RegraDeNegocio

api = Blueprint("api", __name__)


def exige_chave(funcao):
    @wraps(funcao)
    def protegida(*args, **kwargs):
        esperada = current_app.config.get("API_CHAVE")
        recebida = request.headers.get("X-API-Key", "")
        if not esperada or not hmac.compare_digest(recebida.encode(), esperada.encode()):
            return jsonify(erro="Chave de API ausente ou inválida."), 401
        return funcao(*args, **kwargs)
    return protegida


@api.get("/linha")
@exige_chave
def linha():
    """Lotes em produção e os parâmetros que a etapa atual espera receber."""
    lotes = []
    for lote in Lote.query.filter_by(status=StatusLote.EM_PRODUCAO).all():
        etapa = lote.etapa_atual
        lotes.append({
            "lote": lote.codigo, "etapa": etapa.etapa_padrao.nome,
            "ciclo": etapa.ciclos, "ciclos_necessarios": etapa.etapa_padrao.ciclos_necessarios,
            "parametros": [{"id": p.id, "nome": p.nome, "unidade": p.unidade,
                            "alerta_min": p.alerta_min, "alerta_max": p.alerta_max,
                            "espec_min": p.espec_min, "espec_max": p.espec_max}
                           for p in etapa.etapa_padrao.parametros]})
    return jsonify(lotes=lotes)


@api.post("/leituras")
@exige_chave
def receber_leitura():
    """POST /api/leituras  {"lote": "LP-2026-001", "parametro": 3, "valor": 2.1}"""
    dados = request.get_json(silent=True) or {}
    lote = Lote.query.filter_by(codigo=dados.get("lote")).first()
    parametro = db.session.get(ParametroControle, dados.get("parametro") or 0)
    try:
        valor = float(dados["valor"])
    except (KeyError, TypeError, ValueError):
        valor = None
    if valor is not None and not math.isfinite(valor):
        valor = None
    if lote is None or parametro is None or valor is None:
        return jsonify(erro="Informe lote, parametro e valor numérico."), 400
    with trava:
        try:
            leitura = producao.processar_leitura(lote, parametro, valor)
            db.session.commit()
        except RegraDeNegocio as erro:
            db.session.rollback()
            return jsonify(erro=str(erro)), 409
    return jsonify(classificacao=leitura.classificacao.value,
                   status_do_lote=lote.status.value), 201


@api.post("/ciclo")
def ciclo():
    """Modo demonstração: um ciclo do simulador interno, acionado pelo painel."""
    if not current_app.config["DEMO"] or not session.get("usuario_id"):
        return jsonify(erro="Disponível apenas no modo demonstração, com usuário autenticado."), 403
    with trava:
        producao.executar_ciclo()
    return jsonify(pendentes=len(producao.intervencoes_pendentes()))
