"""Serviço de Estoque e Logística."""
from datetime import date, timedelta

from ..models import (Alerta, Cliente, ConsumoInsumo, Expedicao, Item, Lote,
                      LoteInsumo, MovimentacaoEstoque, Perfil, StatusEstoque,
                      StatusLote, TipoMovimentacao, db)
from ..formato import numero
from . import auditoria
from .auditoria import SISTEMA, RegraDeNegocio

DIAS_ALERTA_VALIDADE = 30


def _proximo_codigo(prefixo, modelo):
    return f"{prefixo}-{date.today().year}-{modelo.query.count() + 1:03d}"


# ---------------------------------------------------------------- recebimento
def receber_insumo(usuario, item, fornecedor, lote_fornecedor, validade, quantidade):
    """RF13: todo insumo recebido entra em Quarentena (RN01)."""
    auditoria.exigir_perfil(usuario, Perfil.ALMOXARIFE)
    if quantidade <= 0:
        raise RegraDeNegocio("A quantidade recebida deve ser maior que zero.")
    lote = LoteInsumo(
        codigo=_proximo_codigo("LI", LoteInsumo), item=item, fornecedor=fornecedor,
        lote_fornecedor=lote_fornecedor, validade=validade,
        quantidade_recebida=quantidade, saldo=quantidade,
        status=StatusEstoque.QUARENTENA,
    )
    db.session.add(lote)
    db.session.flush()
    _movimentar(TipoMovimentacao.RECEBIMENTO, quantidade, usuario.login, lote_insumo=lote)
    auditoria.registrar(usuario.login, "RECEBER_INSUMO", lote.codigo,
                        f"{quantidade} {item.unidade} de {item.nome}; entra em Quarentena")
    return lote


def _movimentar(tipo, quantidade, autor, lote_insumo=None, lote=None):
    """RF15: toda alteração de saldo gera uma movimentação."""
    db.session.add(MovimentacaoEstoque(tipo=tipo, quantidade=quantidade, autor=autor,
                                       lote_insumo=lote_insumo, lote=lote))


# ------------------------------------------------------- integração: produção
def lotes_disponiveis_fefo(item, hoje=None):
    """Lotes aprovados, com saldo e dentro da validade, do que vence primeiro (RN02)."""
    hoje = hoje or date.today()
    return (LoteInsumo.query
            .filter(LoteInsumo.item_id == item.id,
                    LoteInsumo.status == StatusEstoque.APROVADO,
                    LoteInsumo.saldo > 0,
                    LoteInsumo.validade >= hoje)
            .order_by(LoteInsumo.validade, LoteInsumo.id).all())


def saldo_aprovado(item, hoje=None):
    return sum(l.saldo for l in lotes_disponiveis_fefo(item, hoje))


def verificar_disponibilidade(formula, hoje=None):
    """RF02: devolve a lista de faltas [(item, falta)]; vazia se há tudo."""
    faltas = []
    for linha in formula.itens:
        disponivel = saldo_aprovado(linha.item, hoje)
        if disponivel < linha.quantidade:
            faltas.append((linha.item, round(linha.quantidade - disponivel, 3)))
    return faltas


def baixar_insumos_fefo(lote, hoje=None):
    """RF03: baixa por FEFO e grava a genealogia do lote (RN10)."""
    for linha in lote.ordem.formula.itens:
        restante = linha.quantidade
        for lote_insumo in lotes_disponiveis_fefo(linha.item, hoje):
            if restante <= 0:
                break
            usado = min(lote_insumo.saldo, restante)
            lote_insumo.saldo = round(lote_insumo.saldo - usado, 3)
            restante = round(restante - usado, 3)
            db.session.add(ConsumoInsumo(lote=lote, lote_insumo=lote_insumo,
                                         quantidade=usado))
            _movimentar(TipoMovimentacao.CONSUMO, usado, SISTEMA,
                        lote_insumo=lote_insumo, lote=lote)
        if restante > 0:  # não deve ocorrer: a disponibilidade foi verificada antes
            raise RegraDeNegocio(f"RF02: saldo insuficiente de {linha.item.nome}.")
    auditoria.registrar(SISTEMA, "BAIXAR_INSUMOS_FEFO", lote.codigo,
                        f"{len(lote.consumos)} lotes de insumo consumidos")
    verificar_estoque_minimo(hoje)


def entrada_producao(lote):
    """RF21: o produto aprovado entra no estoque sem digitação."""
    lote.saldo = lote.quantidade_produzida
    _movimentar(TipoMovimentacao.ENTRADA_PRODUCAO, lote.saldo, SISTEMA, lote=lote)
    auditoria.registrar(SISTEMA, "ENTRADA_PRODUCAO", lote.codigo,
                        f"{numero(lote.saldo)} {lote.produto.unidade} disponíveis para expedição")


# ------------------------------------------------------------------ expedição
def expedir(usuario, produto, cliente, quantidade, hoje=None):
    """RF18: o sistema escolhe os lotes por FEFO; só lote Aprovado sai (RN08)."""
    auditoria.exigir_perfil(usuario, Perfil.ALMOXARIFE)
    hoje = hoje or date.today()
    if quantidade <= 0:
        raise RegraDeNegocio("A quantidade deve ser maior que zero.")
    candidatos = [l for l in Lote.query.filter(Lote.status == StatusLote.APROVADO,
                                               Lote.saldo > 0).order_by(Lote.validade, Lote.id)
                  if l.produto.id == produto.id and l.validade >= hoje]
    if sum(l.saldo for l in candidatos) < quantidade:
        raise RegraDeNegocio(
            "RN08: não há saldo de lotes Aprovados suficiente para esta expedição.")
    expedicoes, restante = [], quantidade
    for lote in candidatos:
        if restante <= 0:
            break
        expedicoes.append(expedir_lote(usuario, lote, cliente, min(lote.saldo, restante), hoje))
        restante -= expedicoes[-1].quantidade
    return expedicoes


def expedir_lote(usuario, lote, cliente, quantidade, hoje=None):
    """Expede de um lote específico. Recusa qualquer lote que não esteja Aprovado."""
    auditoria.exigir_perfil(usuario, Perfil.ALMOXARIFE)
    hoje = hoje or date.today()
    if lote.status != StatusLote.APROVADO:
        auditoria.registrar(SISTEMA, "EXPEDICAO_RECUSADA", lote.codigo,
                            f"status {lote.status.value}; tentativa de {usuario.login}")
        db.session.commit()
        raise RegraDeNegocio(
            f"RN08: o lote {lote.codigo} está {lote.status.value} e não pode ser expedido.")
    if lote.validade < hoje:
        raise RegraDeNegocio(f"RN03: o lote {lote.codigo} está vencido.")
    if quantidade > lote.saldo:
        raise RegraDeNegocio(f"Saldo insuficiente no lote {lote.codigo}.")
    lote.saldo -= quantidade
    if lote.saldo == 0:
        lote.status = StatusLote.EXPEDIDO
    expedicao = Expedicao(lote=lote, cliente=cliente, quantidade=quantidade)
    db.session.add(expedicao)
    _movimentar(TipoMovimentacao.EXPEDICAO, quantidade, usuario.login, lote=lote)
    auditoria.registrar(usuario.login, "EXPEDIR", lote.codigo,
                        f"{numero(quantidade)} {lote.produto.unidade} para {cliente.nome}")
    return expedicao


# -------------------------------------------------------------------- descarte
def descartar_insumo(usuario, lote_insumo, senha, justificativa):
    """RF19: só se descarta o que está reprovado, bloqueado ou vencido."""
    auditoria.exigir_perfil(usuario, Perfil.ALMOXARIFE)
    auditoria.exigir_assinatura(usuario, senha, justificativa)
    if lote_insumo.status not in (StatusEstoque.REPROVADO, StatusEstoque.VENCIDO,
                                  StatusEstoque.BLOQUEADO):
        raise RegraDeNegocio("RF19: apenas lotes reprovados, bloqueados ou vencidos "
                             "podem ser descartados.")
    _movimentar(TipoMovimentacao.DESCARTE, lote_insumo.saldo, usuario.login,
                lote_insumo=lote_insumo)
    lote_insumo.saldo = 0
    lote_insumo.status = StatusEstoque.DESCARTADO
    auditoria.registrar(usuario.login, "DESCARTAR", lote_insumo.codigo, justificativa)


def descartar_lote(usuario, lote, senha, justificativa):
    auditoria.exigir_perfil(usuario, Perfil.ALMOXARIFE)
    auditoria.exigir_assinatura(usuario, senha, justificativa)
    if lote.status not in (StatusLote.REPROVADO, StatusLote.VENCIDO, StatusLote.RECOLHIDO):
        raise RegraDeNegocio("RF19: apenas lotes reprovados, recolhidos ou vencidos "
                             "podem ser descartados.")
    _movimentar(TipoMovimentacao.DESCARTE, lote.saldo, usuario.login, lote=lote)
    lote.saldo = 0
    lote.status = StatusLote.DESCARTADO
    auditoria.registrar(usuario.login, "DESCARTAR", lote.codigo, justificativa)


# ------------------------------------------------------- rotinas automáticas
def rotina_validade(hoje=None):
    """RF16: bloqueia vencidos (RN03) e alerta quem vence em até 30 dias."""
    hoje = hoje or date.today()
    limite = hoje + timedelta(days=DIAS_ALERTA_VALIDADE)
    bloqueados = []
    for li in LoteInsumo.query.filter(LoteInsumo.saldo > 0).all():
        if li.validade < hoje and li.status in (StatusEstoque.QUARENTENA,
                                                StatusEstoque.APROVADO):
            li.status = StatusEstoque.VENCIDO
            bloqueados.append(li.codigo)
            auditoria.registrar(SISTEMA, "BLOQUEAR_VENCIDO", li.codigo,
                                f"validade {li.validade:%d/%m/%Y}")
        elif li.status == StatusEstoque.APROVADO and li.validade <= limite:
            _alertar("VALIDADE_PROXIMA",
                     f"{li.codigo} ({li.item.nome}) vence em {li.validade:%d/%m/%Y}")
    for lote in Lote.query.filter(Lote.status == StatusLote.APROVADO).all():
        if lote.validade < hoje:
            lote.status = StatusLote.VENCIDO
            bloqueados.append(lote.codigo)
            auditoria.registrar(SISTEMA, "BLOQUEAR_VENCIDO", lote.codigo,
                                f"validade {lote.validade:%d/%m/%Y}")
    return bloqueados


def verificar_estoque_minimo(hoje=None):
    """RF17: alerta quando o saldo aprovado fica abaixo do mínimo."""
    for item in Item.query.filter(Item.estoque_minimo > 0).all():
        saldo = saldo_aprovado(item, hoje)
        if saldo < item.estoque_minimo:
            _alertar("ESTOQUE_MINIMO",
                     f"{item.nome}: saldo aprovado de {numero(saldo)} {item.unidade}, "
                     f"abaixo do mínimo de {numero(item.estoque_minimo)}")


def _alertar(tipo, mensagem):
    if not Alerta.query.filter_by(tipo=tipo, mensagem=mensagem).first():
        db.session.add(Alerta(tipo=tipo, mensagem=mensagem))


def clientes():
    return Cliente.query.order_by(Cliente.nome).all()
