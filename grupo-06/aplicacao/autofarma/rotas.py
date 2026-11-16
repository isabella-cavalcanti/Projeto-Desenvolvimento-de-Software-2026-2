"""Interface web. As rotas não contêm regra de negócio: apenas chamam os
serviços e mostram o resultado, inclusive a recusa por uma regra."""
import hmac
import secrets
from datetime import date, datetime

from flask import (Blueprint, abort, current_app, flash, g, redirect,
                   render_template, request, session, url_for)

from .models import (Alerta, Cliente, Decisao, Formula, Item, Leitura, Lote,
                     LoteInsumo, MovimentacaoEstoque, OrdemProducao, Perfil,
                     ProdutoAcabado, Recall, RegistroAuditoria, Resultado,
                     StatusEstoque, StatusLote, Usuario, db)
from . import entrada
from .entrada import trava
from .servicos import auditoria, cadastros, estoque, indicadores, producao, qualidade
from .servicos.auditoria import RegraDeNegocio

web = Blueprint("web", __name__)


# ------------------------------------------------------------------ sessão
def token_csrf():
    """RNF01: cada sessão tem um token que todo formulário precisa devolver."""
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def proteger(blueprint):
    """Sessão, usuário ativo e proteção de formulários para as telas."""
    @blueprint.before_request
    def carregar_usuario():
        g.usuario = db.session.get(Usuario, session.get("usuario_id") or 0)
        if g.usuario is not None and not g.usuario.ativo:   # RN17
            session.clear()
            g.usuario = None
        if g.usuario is None and request.endpoint not in ("web.login", "static"):
            return redirect(url_for("web.login"))
        if request.method == "POST" and current_app.config["CSRF_ATIVO"]:
            enviado = request.form.get("csrf", "")
            if not hmac.compare_digest(enviado, session.get("csrf", "-")):
                abort(400, "Formulário expirado ou inválido. Recarregue a página.")


proteger(web)


@web.app_context_processor
def contexto():
    pendentes = producao.intervencoes_pendentes() if g.get("usuario") else []
    return dict(usuario=g.get("usuario"), pendentes=pendentes, Perfil=Perfil,
                StatusLote=StatusLote, StatusEstoque=StatusEstoque, hoje=date.today(),
                csrf=token_csrf, demo=current_app.config["DEMO"])


def executar(operacao, sucesso):
    """Executa uma operação de negócio em uma transação e informa o resultado."""
    with trava:
        try:
            operacao()
            db.session.commit()
            flash(sucesso, "ok")
        except RegraDeNegocio as erro:
            db.session.rollback()
            flash(str(erro), "erro")


def voltar(padrao):
    """Volta à tela de origem, mas só se ela for desta aplicação."""
    origem = request.referrer or ""
    if origem.startswith(request.host_url):
        return redirect(origem)
    return redirect(url_for(padrao))


@web.after_app_request
def cabecalhos_de_seguranca(resposta):
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("X-Frame-Options", "DENY")
    resposta.headers.setdefault("Referrer-Policy", "same-origin")
    resposta.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; form-action 'self'")
    if request.endpoint != "static":
        resposta.headers.setdefault("Cache-Control", "no-store")
    return resposta


@web.app_errorhandler(400)
@web.app_errorhandler(403)
@web.app_errorhandler(404)
@web.app_errorhandler(500)
def pagina_de_erro(erro):
    codigo = getattr(erro, "code", 500)
    if request.path.startswith("/api/"):
        return {"erro": getattr(erro, "description", "Erro interno.")}, codigo
    if codigo == 500:
        db.session.rollback()
    mensagens = {400: "A requisição não pôde ser aceita. Recarregue a página e tente de novo.",
                 403: "Você não tem acesso a esta operação.",
                 404: "Página não encontrada.",
                 500: "Ocorreu um erro interno. Nada foi gravado."}
    return render_template("erro.html", codigo=codigo, mensagem=mensagens.get(codigo, "")), codigo


@web.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = Usuario.query.filter_by(login=request.form.get("login", "").strip().lower()).first()
        with trava:
            liberado = auditoria.autenticar(usuario, request.form.get("senha"))
            db.session.commit()
        if liberado:
            session.clear()
            session.permanent = True
            session["usuario_id"] = usuario.id
            auditoria.registrar(usuario.login, "LOGIN", "sessão", usuario.perfil.value)
            db.session.commit()
            return redirect(url_for("web.painel"))
        flash("Usuário ou senha inválidos.", "erro")
    usuarios = Usuario.query.filter_by(ativo=True).all() if current_app.config["DEMO"] else []
    return render_template("login.html", usuarios=usuarios)


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


def _so_na_demonstracao():
    if not current_app.config["DEMO"]:
        abort(404)


@web.post("/simulador/ciclo")
def simular_ciclo():
    _so_na_demonstracao()
    with trava:
        producao.executar_ciclo()
    return voltar("web.painel")


@web.post("/simulador/anomalia")
def simular_anomalia():
    _so_na_demonstracao()
    producao.SimuladorDeSensores.anomalia_pendente = True
    flash("Anomalia armada: a próxima leitura sairá fora de especificação.", "atencao")
    return voltar("web.painel")


@web.post("/intervencoes/<int:id>/resolver")
def resolver_intervencao(id):
    from .models import Intervencao
    intervencao = db.get_or_404(Intervencao, id)
    executar(lambda: producao.resolver_intervencao(
        g.usuario, intervencao, entrada.opcao(Decisao, request.form.get("decisao"), "decisão"),
        request.form.get("senha"), entrada.texto(request.form.get("justificativa"), "justificativa", 300)),
        "Decisão registrada.")
    return voltar("web.painel")


# ------------------------------------------------------------------- ordens
@web.route("/ordens")
def ordens():
    return render_template("ordens.html", formulas=Formula.query.all(),
                           ordens=OrdemProducao.query.order_by(OrdemProducao.id.desc()).all())


@web.post("/ordens")
def criar_ordem():
    formula = db.get_or_404(Formula, request.form.get("formula", type=int) or 0)

    def operacao():
        if not cadastros.formula_pronta(formula):
            raise RegraDeNegocio("A fórmula deste produto ainda não tem insumos e roteiro "
                                 "com limites cadastrados.")
        ordem = producao.criar_ordem(g.usuario, formula)
        if not producao.iniciar_ordem(ordem.lote) and ordem.lote.status == StatusLote.PLANEJADO:
            flash("A linha está ocupada: o lote entrou na fila e será iniciado pelo sistema "
                  "quando a linha ficar livre.", "atencao")
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
    item = db.get_or_404(Item, request.form.get("item", type=int) or 0)
    executar(lambda: estoque.receber_insumo(
        g.usuario, item, entrada.texto(request.form.get("fornecedor"), "fornecedor", 80),
        entrada.texto(request.form.get("lote_fornecedor"), "lote do fornecedor", 40),
        entrada.data(request.form.get("validade"), "validade"),
        entrada.numero(request.form.get("quantidade"), "quantidade")),
        "Insumo recebido. O lote entrou em Quarentena e aguarda o Controle de Qualidade.")
    return redirect(url_for("web.ver_estoque"))


@web.post("/estoque/insumo/<int:id>/descartar")
def descartar_insumo(id):
    lote_insumo = db.get_or_404(LoteInsumo, id)
    executar(lambda: estoque.descartar_insumo(
        g.usuario, lote_insumo, request.form.get("senha"),
        entrada.texto(request.form.get("justificativa"), "justificativa", 300)),
        f"Lote {lote_insumo.codigo} descartado.")
    return redirect(url_for("web.ver_estoque"))


@web.post("/estoque/lote/<int:id>/descartar")
def descartar_lote(id):
    lote = db.get_or_404(Lote, id)
    executar(lambda: estoque.descartar_lote(
        g.usuario, lote, request.form.get("senha"),
        entrada.texto(request.form.get("justificativa"), "justificativa", 300)),
        f"Lote {lote.codigo} descartado.")
    return redirect(url_for("web.ver_estoque"))


@web.post("/expedicao")
def expedir():
    produto = db.get_or_404(Item, request.form.get("produto", type=int) or 0)
    cliente = db.get_or_404(Cliente, request.form.get("cliente", type=int) or 0)
    executar(lambda: estoque.expedir(g.usuario, produto, cliente,
                                     entrada.numero(request.form.get("quantidade"), "quantidade")),
             "Expedição registrada. Os lotes foram escolhidos por ordem de validade.")
    return redirect(url_for("web.ver_estoque"))


@web.post("/expedicao/lote/<int:id>")
def expedir_lote(id):
    """Tentativa de expedir um lote específico: mostra a recusa da RN08."""
    lote = db.get_or_404(Lote, id)
    cliente = db.get_or_404(Cliente, request.form.get("cliente", type=int) or 0)
    executar(lambda: estoque.expedir_lote(g.usuario, lote, cliente,
                                          entrada.numero(request.form.get("quantidade"), "quantidade")),
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
    executar(lambda: qualidade.avaliar_insumo(
        g.usuario, lote_insumo, entrada.opcao(Resultado, request.form.get("resultado"), "resultado"),
        request.form.get("senha"), entrada.texto(request.form.get("observacao"), "parecer", 300)),
        f"Avaliação do insumo {lote_insumo.codigo} registrada.")
    return redirect(url_for("web.ver_qualidade"))


@web.post("/qualidade/lote/<int:id>")
def avaliar_lote(id):
    lote = db.get_or_404(Lote, id)
    executar(lambda: qualidade.avaliar_lote(
        g.usuario, lote, entrada.opcao(Resultado, request.form.get("resultado"), "resultado"),
        request.form.get("senha"), entrada.texto(request.form.get("observacao"), "parecer", 300)),
        f"Avaliação do lote {lote.codigo} registrada.")
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
    insumo = db.session.get(LoteInsumo, request.form.get("insumo", type=int) or 0)
    lote = db.session.get(Lote, request.form.get("lote", type=int) or 0)
    executar(lambda: qualidade.iniciar_recall(
        g.usuario, request.form.get("senha"), entrada.texto(request.form.get("motivo"), "motivo", 300),
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


# ---------------------------------------------------- indicadores e relatório
@web.route("/indicadores")
def ver_indicadores():
    """RF29: visão gerencial de produção, qualidade e estoque."""
    return render_template("indicadores.html", i=indicadores.calcular())


@web.route("/lotes/<codigo>/relatorio")
def relatorio_do_lote(codigo):
    """RF30: registro completo do lote, pronto para imprimir."""
    lote = Lote.query.filter_by(codigo=codigo).first_or_404()
    return render_template("relatorio_lote.html", r=qualidade.rastrear_para_tras(lote),
                           emitido_em=datetime.now())


# ----------------------------------------------------------------------- conta
@web.route("/conta", methods=["GET", "POST"])
def conta():
    if request.method == "POST":
        executar(lambda: cadastros.trocar_senha(g.usuario, request.form.get("atual"),
                                                request.form.get("nova")),
                 "Senha alterada.")
        return redirect(url_for("web.conta"))
    return render_template("conta.html")
