"""Trilha de auditoria e assinatura eletrônica (RF25, RN07, RN12, RNF02)."""
import hashlib
from datetime import datetime

from ..models import RegistroAuditoria, db

SISTEMA = "SISTEMA"
HASH_INICIAL = "0" * 64


class RegraDeNegocio(Exception):
    """Operação recusada por uma regra de negócio. A mensagem cita a regra."""


def _calcular_hash(anterior, data_hora, autor, acao, entidade, detalhe):
    texto = "|".join([anterior, data_hora.isoformat(), autor, acao, entidade, detalhe])
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def registrar(autor, acao, entidade, detalhe=""):
    """Acrescenta um registro ligado ao hash do registro anterior."""
    ultimo = RegistroAuditoria.query.order_by(RegistroAuditoria.id.desc()).first()
    anterior = ultimo.hash if ultimo else HASH_INICIAL
    agora = datetime.now()
    registro = RegistroAuditoria(
        data_hora=agora, autor=autor, acao=acao, entidade=entidade, detalhe=detalhe,
        hash_anterior=anterior,
        hash=_calcular_hash(anterior, agora, autor, acao, entidade, detalhe),
    )
    db.session.add(registro)
    db.session.flush()
    return registro


def verificar_cadeia():
    """Recalcula a cadeia. Devolve (True, None) ou (False, id do registro violado)."""
    anterior = HASH_INICIAL
    for r in RegistroAuditoria.query.order_by(RegistroAuditoria.id).all():
        esperado = _calcular_hash(anterior, r.data_hora, r.autor, r.acao,
                                  r.entidade, r.detalhe)
        if r.hash_anterior != anterior or r.hash != esperado:
            return False, r.id
        anterior = r.hash
    return True, None


def exigir_assinatura(usuario, senha, justificativa):
    """RN07: decisão crítica exige nova confirmação da senha e justificativa."""
    if not usuario.conferir_senha(senha):
        raise RegraDeNegocio("RN07: assinatura eletrônica inválida (senha incorreta).")
    if not (justificativa or "").strip():
        raise RegraDeNegocio("RN07: a justificativa é obrigatória.")


def exigir_perfil(usuario, *perfis):
    """RN06 e RN13: somente pessoa autorizada executa a operação."""
    if usuario.perfil not in perfis:
        nomes = " ou ".join(p.value for p in perfis)
        raise RegraDeNegocio(f"RN06: operação exclusiva do perfil {nomes}.")
