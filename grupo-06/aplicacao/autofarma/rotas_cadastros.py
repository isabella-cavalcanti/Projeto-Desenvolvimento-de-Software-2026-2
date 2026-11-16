"""Telas de cadastro: itens, clientes, usuários, fórmulas e limites de processo."""
from flask import Blueprint, g, redirect, render_template, request, url_for

from .models import (Cliente, EtapaPadrao, Formula, Item, ParametroControle, Perfil,
                     ProdutoAcabado, Usuario, db)
from . import entrada
from .rotas import executar, proteger
from .servicos import cadastros as servico

cadastros = Blueprint("cadastros", __name__, url_prefix="/cadastros")
proteger(cadastros)


def _numero(campo, padrao=None):
    return entrada.numero(request.form.get(campo), campo, padrao=padrao)


def _assinatura():
    return request.form.get("senha"), entrada.texto(request.form.get("justificativa"), "justificativa", 300)


# ----------------------------------------------------------------------- itens
@cadastros.route("/itens")
def itens():
    return render_template("cad_itens.html", itens=Item.query.order_by(Item.tipo, Item.codigo).all(),
                           clientes=Cliente.query.order_by(Cliente.nome).all(),
                           editar=db.session.get(Item, request.args.get("editar", type=int) or 0))


@cadastros.post("/itens")
def salvar_item():
    item = db.session.get(Item, request.form.get("id", type=int) or 0)
    tipo = item.tipo if item else request.form.get("tipo")
    executar(lambda: servico.salvar_item(
        g.usuario, tipo, entrada.texto(request.form.get("codigo"), "código", 20),
        entrada.texto(request.form.get("nome"), "nome", 80),
        entrada.texto(request.form.get("unidade"), "unidade", 10), _numero("estoque_minimo", 0),
        item=item, validade_meses=request.form.get("validade_meses", type=int)),
        "Item salvo.")
    return redirect(url_for("cadastros.itens"))


@cadastros.post("/clientes")
def salvar_cliente():
    cliente = db.session.get(Cliente, request.form.get("id", type=int) or 0)
    executar(lambda: servico.salvar_cliente(
        g.usuario, entrada.texto(request.form.get("nome"), "nome", 80),
        entrada.texto(request.form.get("cidade"), "cidade", 60), cliente=cliente),
             "Cliente salvo.")
    return redirect(url_for("cadastros.itens"))


# -------------------------------------------------------------------- usuários
@cadastros.route("/usuarios")
def usuarios():
    return render_template("cad_usuarios.html", usuarios=Usuario.query.order_by(Usuario.nome).all())


@cadastros.post("/usuarios")
def criar_usuario():
    executar(lambda: servico.criar_usuario(
        g.usuario, entrada.texto(request.form.get("nome"), "nome", 80),
        entrada.texto(request.form.get("login"), "usuário", 40),
        entrada.opcao(Perfil, request.form.get("perfil"), "perfil"), request.form.get("senha")),
        "Usuário criado.")
    return redirect(url_for("cadastros.usuarios"))


@cadastros.post("/usuarios/<int:id>")
def alterar_usuario(id):
    alvo = db.get_or_404(Usuario, id)
    acao = request.form.get("acao")
    executar(lambda: servico.alterar_usuario(
        g.usuario, alvo,
        perfil=entrada.opcao(Perfil, request.form.get("perfil"), "perfil") if acao == "perfil" else None,
        ativo={"desativar": False, "reativar": True}.get(acao),
        nova_senha=request.form.get("nova_senha") if acao == "senha" else None),
        f"Usuário {alvo.login} atualizado.")
    return redirect(url_for("cadastros.usuarios"))


# ------------------------------------------------------------------- fórmulas
@cadastros.route("/formulas")
def formulas():
    com_formula = {f.produto_id for f in Formula.query.all()}
    return render_template(
        "cad_formulas.html", formulas=Formula.query.all(),
        sem_formula=[p for p in ProdutoAcabado.query.all() if p.id not in com_formula])


@cadastros.post("/formulas")
def criar_formula():
    produto = db.get_or_404(Item, request.form.get("produto", type=int))
    executar(lambda: servico.criar_formula(g.usuario, produto, _numero("rendimento"), *_assinatura()),
             "Fórmula criada. Inclua os insumos, as etapas e os limites.")
    formula = Formula.query.filter_by(produto_id=produto.id).first()
    return redirect(url_for("cadastros.formula", id=formula.id) if formula
                    else url_for("cadastros.formulas"))


@cadastros.route("/formulas/<int:id>")
def formula(id):
    f = db.get_or_404(Formula, id)
    return render_template("cad_formula.html", f=f, pronta=servico.formula_pronta(f),
                           insumos=Item.query.filter(Item.tipo != "produto_acabado")
                           .order_by(Item.codigo).all())


@cadastros.post("/formulas/<int:id>/rendimento")
def rendimento(id):
    f = db.get_or_404(Formula, id)
    executar(lambda: servico.definir_rendimento(g.usuario, f, _numero("rendimento"), *_assinatura()),
             "Rendimento alterado.")
    return redirect(url_for("cadastros.formula", id=id))


@cadastros.post("/formulas/<int:id>/itens")
def item_da_formula(id):
    f = db.get_or_404(Formula, id)
    item = db.get_or_404(Item, request.form.get("item", type=int))
    executar(lambda: servico.definir_item_da_formula(g.usuario, f, item, _numero("quantidade"),
                                                     *_assinatura()),
             "Fórmula alterada.")
    return redirect(url_for("cadastros.formula", id=id))


@cadastros.post("/formulas/<int:id>/etapas")
def etapa(id):
    f = db.get_or_404(Formula, id)
    executar(lambda: servico.adicionar_etapa(g.usuario, f, entrada.texto(request.form.get("nome"), "etapa", 60),
                                             entrada.inteiro(request.form.get("ciclos"), "ciclos", 1, 50),
                                             *_assinatura()),
             "Etapa incluída no fim do roteiro.")
    return redirect(url_for("cadastros.formula", id=id))


@cadastros.post("/etapas/<int:id>/parametros")
def parametro(id):
    etapa_padrao = db.get_or_404(EtapaPadrao, id)
    existente = db.session.get(ParametroControle, request.form.get("parametro", type=int) or 0)
    executar(lambda: servico.salvar_parametro(
        g.usuario, etapa_padrao, entrada.texto(request.form.get("nome"), "parâmetro", 60),
        entrada.texto(request.form.get("unidade"), "unidade", 10),
        _numero("alerta_min"), _numero("alerta_max"), _numero("espec_min"), _numero("espec_max"),
        *_assinatura(), parametro=existente),
        "Limites de processo salvos.")
    return redirect(url_for("cadastros.formula", id=etapa_padrao.formula_id))
