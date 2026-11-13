"""Interface web. As rotas não contêm regra de negócio: apenas chamam os
serviços e mostram o resultado, inclusive a recusa por uma regra."""
from datetime import date, datetime
from functools import wraps

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)

from .models import (Alerta, Cliente, Decisao, Formula, Item, Leitura, Lote,
                     LoteInsumo, MovimentacaoEstoque, OrdemProducao, Perfil,
                     ProdutoAcabado, Recall, RegistroAuditoria, Resultado,
                     StatusEstoque, StatusLote, Usuario, db)
from .servicos import auditoria, estoque, producao, qualidade
from .servicos.auditoria import RegraDeNegocio

web = Blueprint("web", __name__)


# ------------------------------------------------------------------ sessão
@web.before_request
def carregar_usuario():
    g.usuario = db.session.get(Usuario, session.get("usuario_id") or 0)
    if g.usuario is None and request.endpoint not in ("web.login", "static"):
        return redirect(url_for("web.login"))


@web.app_context_processor
def contexto():
    pendentes = producao.intervencoes_pendentes() if g.get("usuario") else []
    return dict(usuario=g.get("usuario"), pendentes=pendentes, Perfil=Perfil,
                StatusLote=StatusLote, StatusEstoque=StatusEstoque, hoje=date.today())


def executar(operacao, sucesso):
    """Executa uma operação de negócio em uma transação e informa o resultado."""
    try:
        operacao()
        db.session.commit()
        flash(sucesso, "ok")
    except RegraDeNegocio as erro:
        db.session.rollback()
        flash(str(erro), "erro")


def voltar(padrao):
    return redirect(request.referrer or url_for(padrao))


@web.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = Usuario.query.filter_by(login=request.form.get("login", "")).first()
        if usuario and usuario.conferir_senha(request.form.get("senha")):
            session.clear()
            session.permanent = True
            session["usuario_id"] = usuario.id
            auditoria.registrar(usuario.login, "LOGIN", "sessão", usuario.perfil.value)
            db.session.commit()
            return redirect(url_for("web.painel"))
        flash("Usuário ou senha inválidos.", "erro")
    return render_template("login.html", usuarios=Usuario.query.all())


@web.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("web.login"))


# ------------------------------------------------------------------- painel
@web.route("/")
def painel():
    """RF12: etapa atual, leituras, alertas e fila de intervenções."""
    em_linha = (Lote.query.filter(Lote.status.in_([
        StatusLote.EM_PRODUCAO, StatusLote.AGUARDANDO_INTERVENCAO,
        StatusLote.AGUARDANDO_MATERIAL])).order_by(Lote.id).all())
    leituras = Leitura.query.order_by(Leitura.id.desc()).limit(10).all()
    alertas = Alerta.query.order_by(Alerta.id.desc()).limit(6).all()
    return render_template("painel.html", em_linha=em_linha, leituras=leituras,
                           alertas=alertas, Decisao=Decisao,
                           anomalia=producao.SimuladorDeSensores.anomalia_pendente,
                           agora=datetime.now())


@web.post("/simulador/ciclo")
def simular_ciclo():
    producao.executar_ciclo()
    return voltar("web.painel")


@web.post("/simulador/anomalia")
def simular_anomalia():
    producao.SimuladorDeSensores.anomalia_pendente = True
    flash("Anomalia armada: a próxima leitura sairá fora de especificação.", "atencao")
    return voltar("web.painel")


@web.post("/intervencoes/<int:id>/resolver")
def resolver_intervencao(id):
    from .models import Intervencao
    intervencao = db.get_or_404(Intervencao, id)
    decisao = Decisao[request.form["decisao"]]
    executar(lambda: producao.resolver_intervencao(
        g.usuario, intervencao, decisao, request.form.get("senha"),
        request.form.get("justificativa")),
        f"Decisão registrada: {decisao.value}.")
    return voltar("web.painel")


# ------------------------------------------------------------------- ordens
@web.route("/ordens")
def ordens():
    return render_template("ordens.html", formulas=Formula.query.all(),
                           ordens=OrdemProducao.query.order_by(OrdemProducao.id.desc()).all())


@web.post("/ordens")
def criar_ordem():
    formula = db.get_or_404(Formula, int(request.form["formula"]))

    def operacao():
        ordem = producao.criar_ordem(g.usuario, formula)
        producao.iniciar_ordem(ordem.lote)
    executar(operacao, "Ordem criada. O sistema verificou o estoque e assumiu a condução do lote.")
    return redirect(url_for("web.ordens"))


# ------------------------------------------------------------------ estoque
@web.route("/estoque")
def ver_estoque():
    return render_template(
        "estoque.html", itens=Item.query.order_by(Item.codigo).all(),
        insumos=LoteInsumo.query.order_by(LoteInsumo.item_id, LoteInsumo.validade).all(),
        lotes=Lote.query.filter(Lote.quantidade_produzida > 0).order_by(Lote.id).all(),
        movimentacoes=MovimentacaoEstoque.query.order_by(
            MovimentacaoEstoque.id.desc()).limit(12).all(),
        saldo_aprovado=estoque.saldo_aprovado, clientes=estoque.clientes(),
        produtos=ProdutoAcabado.query.all())


@web.post("/estoque/receber")
def receber_insumo():
    item = db.get_or_404(Item, int(request.form["item"]))
    executar(lambda: estoque.receber_insumo(
        g.usuario, item, request.form["fornecedor"], request.form["lote_fornecedor"],
        date.fromisoformat(request.form["validade"]), float(request.form["quantidade"])),
        "Insumo recebido. O lote entrou em Quarentena e aguarda o Controle de Qualidade.")
    return redirect(url_for("web.ver_estoque"))


@web.post("/estoque/insumo/<int:id>/descartar")
def descartar_insumo(id):
    lote_insumo = db.get_or_404(LoteInsumo, id)
    executar(lambda: estoque.descartar_insumo(
        g.usuario, lote_insumo, request.form.get("senha"), request.form.get("justificativa")),
        f"Lote {lote_insumo.codigo} descartado.")
    return redirect(url_for("web.ver_estoque"))


@web.post("/estoque/lote/<int:id>/descartar")
def descartar_lote(id):
    lote = db.get_or_404(Lote, id)
    executar(lambda: estoque.descartar_lote(
        g.usuario, lote, request.form.get("senha"), request.form.get("justificativa")),
        f"Lote {lote.codigo} descartado.")
    return redirect(url_for("web.ver_estoque"))


@web.post("/expedicao")
def expedir():
    produto = db.get_or_404(Item, int(request.form["produto"]))
    cliente = db.get_or_404(Cliente, int(request.form["cliente"]))
    executar(lambda: estoque.expedir(g.usuario, produto, cliente,
                                     float(request.form["quantidade"])),
             "Expedição registrada. Os lotes foram escolhidos por ordem de validade.")
    return redirect(url_for("web.ver_estoque"))


@web.post("/expedicao/lote/<int:id>")
def expedir_lote(id):
    """Tentativa de expedir um lote específico: mostra a recusa da RN08."""
    lote = db.get_or_404(Lote, id)
    cliente = db.get_or_404(Cliente, int(request.form["cliente"]))
    executar(lambda: estoque.expedir_lote(g.usuario, lote, cliente,
                                          float(request.form["quantidade"])),
             f"Expedição do lote {lote.codigo} registrada.")
    return redirect(url_for("web.ver_estoque"))


# ---------------------------------------------------------------- qualidade
@web.route("/qualidade")
def ver_qualidade():
    return render_template("qualidade.html", Resultado=Resultado,
                           insumos=qualidade.insumos_em_quarentena(),
                           lotes=qualidade.lotes_em_quarentena())


@web.post("/qualidade/insumo/<int:id>")
def avaliar_insumo(id):
    lote_insumo = db.get_or_404(LoteInsumo, id)
    resultado = Resultado[request.form["resultado"]]
    executar(lambda: qualidade.avaliar_insumo(
        g.usuario, lote_insumo, resultado, request.form.get("senha"),
        request.form.get("observacao")),
        f"Insumo {lote_insumo.codigo}: {resultado.value}.")
    return redirect(url_for("web.ver_qualidade"))


@web.post("/qualidade/lote/<int:id>")
def avaliar_lote(id):
    lote = db.get_or_404(Lote, id)
    resultado = Resultado[request.form["resultado"]]
    executar(lambda: qualidade.avaliar_lote(
        g.usuario, lote, resultado, request.form.get("senha"),
        request.form.get("observacao")),
        f"Lote {lote.codigo}: {resultado.value}.")
    return redirect(url_for("web.ver_qualidade"))


# ----------------------------------------------------------- rastreabilidade
@web.route("/rastreabilidade")
def rastreabilidade():
    lote = Lote.query.filter_by(codigo=request.args.get("lote")).first()
    insumo = LoteInsumo.query.filter_by(codigo=request.args.get("insumo")).first()
    return render_template(
        "rastreabilidade.html", lotes=Lote.query.order_by(Lote.id).all(),
        insumos=LoteInsumo.query.order_by(LoteInsumo.id).all(),
        para_tras=qualidade.rastrear_para_tras(lote) if lote else None,
        para_frente=qualidade.rastrear_para_frente(insumo) if insumo else None,
        recalls=Recall.query.order_by(Recall.id.desc()).all())


@web.post("/recall")
def iniciar_recall():
    insumo = db.session.get(LoteInsumo, int(request.form.get("insumo") or 0))
    lote = db.session.get(Lote, int(request.form.get("lote") or 0))
    executar(lambda: qualidade.iniciar_recall(
        g.usuario, request.form.get("senha"), request.form.get("motivo"),
        lote_insumo=insumo, lote=lote),
        "Recall iniciado. O sistema bloqueou os saldos e listou os clientes afetados.")
    return voltar("web.rastreabilidade")


# ------------------------------------------------------------------ auditoria
@web.route("/auditoria")
def ver_auditoria():
    integra, violado = auditoria.verificar_cadeia()
    registros = RegistroAuditoria.query.order_by(RegistroAuditoria.id.desc()).limit(200).all()
    return render_template("auditoria.html", registros=registros, integra=integra,
                           violado=violado, total=RegistroAuditoria.query.count())
