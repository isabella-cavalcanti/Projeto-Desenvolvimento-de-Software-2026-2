"""API REST (RNF09): porta de entrada das leituras da linha.

No protótipo quem chama é o simulador. Em produção, o sistema supervisório
da fábrica enviaria as leituras para o mesmo endereço.
"""
from flask import Blueprint, jsonify, request

from .models import Lote, ParametroControle, db
from .servicos import producao
from .servicos.auditoria import RegraDeNegocio

api = Blueprint("api", __name__)


@api.post("/leituras")
def receber_leitura():
    """POST /api/leituras  {"lote": "LP-2026-001", "parametro": 3, "valor": 2.1}"""
    dados = request.get_json(silent=True) or {}
    lote = Lote.query.filter_by(codigo=dados.get("lote")).first()
    parametro = db.session.get(ParametroControle, dados.get("parametro") or 0)
    if lote is None or parametro is None or "valor" not in dados:
        return jsonify(erro="Informe lote, parametro e valor."), 400
    try:
        leitura = producao.processar_leitura(lote, parametro, float(dados["valor"]))
        db.session.commit()
    except RegraDeNegocio as erro:
        db.session.rollback()
        return jsonify(erro=str(erro)), 409
    return jsonify(classificacao=leitura.classificacao.value,
                   status_do_lote=lote.status.value), 201


@api.post("/ciclo")
def ciclo():
    """Executa um ciclo do motor autônomo (usado pelo modo automático do painel)."""
    producao.executar_ciclo()
    return jsonify(pendentes=len(producao.intervencoes_pendentes()))
