"""Serviço de Cadastros: itens, clientes, usuários, fórmulas e limites de processo.

Os cadastros que afetam a qualidade do produto (fórmula, roteiro e limites)
são alterados somente pela Gerência da Qualidade, com assinatura (RN07).
"""
from ..formato import numero
from ..models import (Cliente, EtapaPadrao, Formula, Item, ItemFormula, Lote,
                      MateriaPrima, MaterialEmbalagem, ParametroControle, Perfil,
                      ProdutoAcabado, StatusLote, Usuario, db)
from . import auditoria
from .auditoria import RegraDeNegocio

SENHA_MINIMA = 8
TIPOS_DE_ITEM = {"materia_prima": MateriaPrima, "embalagem": MaterialEmbalagem,
                 "produto_acabado": ProdutoAcabado}
EM_LINHA = (StatusLote.EM_PRODUCAO, StatusLote.AGUARDANDO_INTERVENCAO,
            StatusLote.AGUARDANDO_MATERIAL)


def _texto(valor, campo):
    valor = (valor or "").strip()
    if not valor:
        raise RegraDeNegocio(f"O campo {campo} é obrigatório.")
    return valor


# ----------------------------------------------------------------------- itens
def salvar_item(usuario, tipo, codigo, nome, unidade, estoque_minimo, item=None,
                validade_meses=None):
    """RF26: insumos pelo Almoxarife; produtos acabados pela Gerência da Qualidade."""
    if tipo not in TIPOS_DE_ITEM:
        raise RegraDeNegocio("Tipo de item inválido.")
    if tipo == "produto_acabado":
        auditoria.exigir_perfil(usuario, Perfil.GERENTE_QUALIDADE)
    else:
        auditoria.exigir_perfil(usuario, Perfil.ALMOXARIFE)
    codigo, nome, unidade = _texto(codigo, "código"), _texto(nome, "nome"), _texto(unidade, "unidade")
    if estoque_minimo < 0:
        raise RegraDeNegocio("O estoque mínimo não pode ser negativo.")
    outro = Item.query.filter_by(codigo=codigo).first()
    if outro is not None and outro is not item:
        raise RegraDeNegocio(f"Já existe um item com o código {codigo}.")
    novo = item is None
    if novo:
        item = TIPOS_DE_ITEM[tipo](codigo=codigo)
        db.session.add(item)
    item.codigo, item.nome, item.unidade, item.estoque_minimo = codigo, nome, unidade, estoque_minimo
    if tipo == "produto_acabado":
        if not validade_meses or validade_meses <= 0:
            raise RegraDeNegocio("Informe a validade do produto em meses.")
        item.validade_meses = validade_meses
    db.session.flush()
    auditoria.registrar(usuario.login, "CADASTRAR_ITEM" if novo else "ALTERAR_ITEM", codigo,
                        f"{nome}; mínimo {numero(estoque_minimo)} {unidade}")
    return item


def salvar_cliente(usuario, nome, cidade, cliente=None):
    """RF26: clientes são mantidos pelo Almoxarife."""
    auditoria.exigir_perfil(usuario, Perfil.ALMOXARIFE)
    nome, cidade = _texto(nome, "nome"), _texto(cidade, "cidade")
    novo = cliente is None
    if novo:
        cliente = Cliente()
        db.session.add(cliente)
    cliente.nome, cliente.cidade = nome, cidade
    db.session.flush()
    auditoria.registrar(usuario.login, "CADASTRAR_CLIENTE" if novo else "ALTERAR_CLIENTE",
                        nome, cidade)
    return cliente


# -------------------------------------------------------------------- usuários
def validar_senha(senha):
    if len(senha or "") < SENHA_MINIMA:
        raise RegraDeNegocio(f"RNF01: a senha deve ter pelo menos {SENHA_MINIMA} caracteres.")


def criar_usuario(admin, nome, login, perfil, senha):
    """RF28: somente o Administrador cria usuários."""
    auditoria.exigir_perfil(admin, Perfil.ADMINISTRADOR)
    nome, login = _texto(nome, "nome"), _texto(login, "usuário").lower()
    if Usuario.query.filter_by(login=login).first():
        raise RegraDeNegocio(f"Já existe o usuário {login}.")
    validar_senha(senha)
    usuario = Usuario(nome=nome, login=login, perfil=perfil, ativo=True)
    usuario.definir_senha(senha)
    db.session.add(usuario)
    db.session.flush()
    auditoria.registrar(admin.login, "CRIAR_USUARIO", login, perfil.value)
    return usuario


def alterar_usuario(admin, usuario, perfil=None, ativo=None, nova_senha=None):
    """RF28 e RN17: usuário nunca é excluído, apenas desativado."""
    auditoria.exigir_perfil(admin, Perfil.ADMINISTRADOR)
    if usuario.id == admin.id and (ativo is False or (perfil and perfil != admin.perfil)):
        raise RegraDeNegocio("RN17: o administrador não pode desativar a si mesmo "
                             "nem mudar o próprio perfil.")
    mudancas = []
    if perfil is not None and perfil != usuario.perfil:
        mudancas.append(f"perfil: {usuario.perfil.value} para {perfil.value}")
        usuario.perfil = perfil
    if ativo is not None and ativo != usuario.ativo:
        mudancas.append("reativado" if ativo else "desativado")
        usuario.ativo = ativo
    if nova_senha:
        validar_senha(nova_senha)
        usuario.definir_senha(nova_senha)
        mudancas.append("senha redefinida")
    if mudancas:
        auditoria.registrar(admin.login, "ALTERAR_USUARIO", usuario.login, "; ".join(mudancas))
    return usuario


def trocar_senha(usuario, senha_atual, nova_senha):
    if not usuario.conferir_senha(senha_atual):
        raise RegraDeNegocio("A senha atual não confere.")
    validar_senha(nova_senha)
    usuario.definir_senha(nova_senha)
    auditoria.registrar(usuario.login, "TROCAR_SENHA", usuario.login, "")


# ---------------------------------------------------------- fórmula e limites
def _exigir_formula_livre(formula):
    """RN16: não se altera fórmula, roteiro ou limite com lote na linha."""
    for lote in Lote.query.filter(Lote.status.in_(EM_LINHA)).all():
        if lote.ordem.formula_id == formula.id:
            raise RegraDeNegocio(f"RN16: o lote {lote.codigo} está na linha; conclua-o antes "
                                 "de alterar a fórmula, o roteiro ou os limites.")


def _gerente_assina(usuario, senha, justificativa, formula=None):
    auditoria.exigir_perfil(usuario, Perfil.GERENTE_QUALIDADE)
    auditoria.exigir_assinatura(usuario, senha, justificativa)
    if formula is not None:
        _exigir_formula_livre(formula)


def criar_formula(usuario, produto, rendimento, senha, justificativa):
    """RF27: cada produto acabado possui uma fórmula-mestra."""
    _gerente_assina(usuario, senha, justificativa)
    if not isinstance(produto, ProdutoAcabado):
        raise RegraDeNegocio("A fórmula deve ser de um produto acabado.")
    if Formula.query.filter_by(produto_id=produto.id).first():
        raise RegraDeNegocio(f"O produto {produto.nome} já possui fórmula.")
    if rendimento <= 0:
        raise RegraDeNegocio("O rendimento deve ser maior que zero.")
    formula = Formula(produto=produto, versao="1.0", rendimento=rendimento)
    db.session.add(formula)
    db.session.flush()
    auditoria.registrar(usuario.login, "CRIAR_FORMULA", produto.codigo, justificativa)
    return formula


def _nova_versao(formula, usuario, acao, detalhe, justificativa):
    maior, menor = (formula.versao.split(".") + ["0"])[:2]
    formula.versao = f"{maior}.{int(menor) + 1}"
    auditoria.registrar(usuario.login, acao, formula.produto.codigo,
                        f"{detalhe}; versão {formula.versao}. {justificativa}")


def definir_item_da_formula(usuario, formula, item, quantidade, senha, justificativa):
    """RF27: inclui, altera ou remove (quantidade zero) um insumo da fórmula."""
    _gerente_assina(usuario, senha, justificativa, formula)
    if isinstance(item, ProdutoAcabado):
        raise RegraDeNegocio("Um produto acabado não pode ser insumo da fórmula.")
    if quantidade < 0:
        raise RegraDeNegocio("A quantidade não pode ser negativa.")
    linha = next((l for l in formula.itens if l.item_id == item.id), None)
    if quantidade == 0:
        if linha is not None:
            db.session.delete(linha)
        detalhe = f"{item.nome} removido"
    else:
        if linha is None:
            linha = ItemFormula(formula=formula, item=item)
            db.session.add(linha)
        linha.quantidade = quantidade
        detalhe = f"{item.nome}: {numero(quantidade)} {item.unidade} por lote"
    _nova_versao(formula, usuario, "ALTERAR_FORMULA", detalhe, justificativa)


def definir_rendimento(usuario, formula, rendimento, senha, justificativa):
    _gerente_assina(usuario, senha, justificativa, formula)
    if rendimento <= 0:
        raise RegraDeNegocio("O rendimento deve ser maior que zero.")
    formula.rendimento = rendimento
    _nova_versao(formula, usuario, "ALTERAR_FORMULA", f"rendimento {numero(rendimento)}", justificativa)


def adicionar_etapa(usuario, formula, nome, ciclos, senha, justificativa):
    """RF27: a nova etapa entra no fim do roteiro."""
    _gerente_assina(usuario, senha, justificativa, formula)
    nome = _texto(nome, "nome da etapa")
    if ciclos < 1:
        raise RegraDeNegocio("A etapa precisa de pelo menos um ciclo de leituras.")
    etapa = EtapaPadrao(formula=formula, ordem=len(formula.etapas) + 1, nome=nome,
                        ciclos_necessarios=ciclos)
    db.session.add(etapa)
    _nova_versao(formula, usuario, "ALTERAR_ROTEIRO", f"etapa {etapa.ordem} {nome}", justificativa)
    return etapa


def validar_limites(alerta_min, alerta_max, espec_min, espec_max):
    """RN15: a faixa de alerta fica dentro da faixa de especificação."""
    if not (espec_min <= alerta_min < alerta_max <= espec_max):
        raise RegraDeNegocio("RN15: os limites devem respeitar especificação mínima ≤ alerta "
                             "mínimo < alerta máximo ≤ especificação máxima.")


def salvar_parametro(usuario, etapa_padrao, nome, unidade, alerta_min, alerta_max,
                     espec_min, espec_max, senha, justificativa, parametro=None):
    """RF27: os limites de processo são dados, alterados com assinatura (RNF10)."""
    _gerente_assina(usuario, senha, justificativa, etapa_padrao.formula)
    nome, unidade = _texto(nome, "parâmetro"), _texto(unidade, "unidade")
    validar_limites(alerta_min, alerta_max, espec_min, espec_max)
    if parametro is None:
        parametro = ParametroControle(etapa_padrao=etapa_padrao)
        db.session.add(parametro)
        antes = "novo"
    else:
        antes = (f"antes {numero(parametro.espec_min)} a {numero(parametro.espec_max)} "
                 f"{parametro.unidade}")
    parametro.nome, parametro.unidade = nome, unidade
    parametro.alerta_min, parametro.alerta_max = alerta_min, alerta_max
    parametro.espec_min, parametro.espec_max = espec_min, espec_max
    _nova_versao(etapa_padrao.formula, usuario, "ALTERAR_LIMITE",
                 f"{nome}: {numero(espec_min)} a {numero(espec_max)} {unidade} ({antes})",
                 justificativa)
    return parametro


def formula_pronta(formula):
    """Uma ordem só pode ser criada se a fórmula tem insumos e roteiro com limites."""
    return bool(formula.itens) and bool(formula.etapas) and all(e.parametros for e in formula.etapas)
