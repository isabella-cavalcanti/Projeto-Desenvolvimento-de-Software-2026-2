"""Modelo de domínio do AutoFarma.

Os nomes das classes, dos atributos e dos estados são os mesmos do
diagrama de classes e do diagrama de estado (docs/diagramas).
"""
import enum
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


# --------------------------------------------------------------------------
# Enumerações
# --------------------------------------------------------------------------
class Perfil(enum.Enum):
    PLANEJADOR = "Planejador de Produção"
    SUPERVISOR = "Supervisor de Produção"
    ANALISTA_CQ = "Analista de Controle de Qualidade"
    ALMOXARIFE = "Almoxarife"
    GERENTE_QUALIDADE = "Gerente da Qualidade"


class StatusEstoque(enum.Enum):
    """Situação de um lote de insumo no almoxarifado."""
    QUARENTENA = "Quarentena"
    APROVADO = "Aprovado"
    REPROVADO = "Reprovado"
    BLOQUEADO = "Bloqueado"
    VENCIDO = "Vencido"
    DESCARTADO = "Descartado"


class StatusLote(enum.Enum):
    """Ciclo de vida do lote de produto (diagrama de estado)."""
    PLANEJADO = "Planejado"
    AGUARDANDO_MATERIAL = "Aguardando Material"
    EM_PRODUCAO = "Em Produção"
    AGUARDANDO_INTERVENCAO = "Aguardando Intervenção"
    EM_QUARENTENA = "Em Quarentena"
    APROVADO = "Aprovado"
    EXPEDIDO = "Expedido"
    REPROVADO = "Reprovado"
    RECOLHIDO = "Recolhido"
    VENCIDO = "Vencido"
    DESCARTADO = "Descartado"


class StatusEtapa(enum.Enum):
    PENDENTE = "Pendente"
    EM_EXECUCAO = "Em execução"
    CONCLUIDA = "Concluída"
    INTERROMPIDA = "Interrompida"


class Classificacao(enum.Enum):
    CONFORME = "Conforme"
    ALERTA = "Alerta"
    FORA_DE_ESPECIFICACAO = "Fora de Especificação"


class TipoIntervencao(enum.Enum):
    DESVIO_PROCESSO = "Desvio de processo"
    FALTA_MATERIAL = "Falta de material"


class StatusIntervencao(enum.Enum):
    ABERTA = "Aberta"
    ESCALONADA = "Escalonada"
    RESOLVIDA = "Resolvida"


class Decisao(enum.Enum):
    RETOMAR = "Retomar a linha"
    REPROCESSAR = "Reprocessar a etapa"
    SEGREGAR = "Segregar o lote"
    MATERIAL_DISPONIVEL = "Material disponível"


class TipoMovimentacao(enum.Enum):
    RECEBIMENTO = "Recebimento"
    CONSUMO = "Consumo na produção"
    ENTRADA_PRODUCAO = "Entrada de produção"
    EXPEDICAO = "Expedição"
    DESCARTE = "Descarte"


class Resultado(enum.Enum):
    APROVADO = "Aprovado"
    REPROVADO = "Reprovado"


# --------------------------------------------------------------------------
# Transversal
# --------------------------------------------------------------------------
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    login = db.Column(db.String(40), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.Enum(Perfil), nullable=False)

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)  # RNF01

    def conferir_senha(self, senha):
        return check_password_hash(self.senha_hash, senha or "")


class RegistroAuditoria(db.Model):
    """Trilha de auditoria encadeada por hash (RF25, RN12, RNF02)."""
    id = db.Column(db.Integer, primary_key=True)
    data_hora = db.Column(db.DateTime, nullable=False)
    autor = db.Column(db.String(80), nullable=False)  # login ou "SISTEMA"
    acao = db.Column(db.String(60), nullable=False)
    entidade = db.Column(db.String(60), nullable=False)
    detalhe = db.Column(db.String(400), nullable=False, default="")
    hash_anterior = db.Column(db.String(64), nullable=False)
    hash = db.Column(db.String(64), nullable=False)


@event.listens_for(RegistroAuditoria, "before_update")
@event.listens_for(RegistroAuditoria, "before_delete")
def _auditoria_imutavel(mapper, connection, target):
    raise PermissionError("RN12: registros da trilha de auditoria são imutáveis.")


class Alerta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(40), nullable=False)
    mensagem = db.Column(db.String(300), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.now)


# --------------------------------------------------------------------------
# Estoque e Logística
# --------------------------------------------------------------------------
class Item(db.Model):
    """Classe abstrata: MateriaPrima, MaterialEmbalagem e ProdutoAcabado."""
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    nome = db.Column(db.String(80), nullable=False)
    unidade = db.Column(db.String(10), nullable=False)
    estoque_minimo = db.Column(db.Float, nullable=False, default=0)
    tipo = db.Column(db.String(20), nullable=False)
    __mapper_args__ = {"polymorphic_on": tipo, "polymorphic_identity": "item"}


class MateriaPrima(Item):
    __mapper_args__ = {"polymorphic_identity": "materia_prima"}


class MaterialEmbalagem(Item):
    __mapper_args__ = {"polymorphic_identity": "embalagem"}


class ProdutoAcabado(Item):
    validade_meses = db.Column(db.Integer, default=24)
    __mapper_args__ = {"polymorphic_identity": "produto_acabado"}


class LoteInsumo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    item_id = db.Column(db.ForeignKey("item.id"), nullable=False)
    fornecedor = db.Column(db.String(80), nullable=False)
    lote_fornecedor = db.Column(db.String(40), nullable=False)
    validade = db.Column(db.Date, nullable=False)
    quantidade_recebida = db.Column(db.Float, nullable=False)
    saldo = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(StatusEstoque), nullable=False,
                       default=StatusEstoque.QUARENTENA)  # RN01
    recebido_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    item = db.relationship(Item)


class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    cidade = db.Column(db.String(60), nullable=False)


class MovimentacaoEstoque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.Enum(TipoMovimentacao), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, nullable=False, default=datetime.now)
    autor = db.Column(db.String(80), nullable=False)
    lote_insumo_id = db.Column(db.ForeignKey("lote_insumo.id"))
    lote_id = db.Column(db.ForeignKey("lote.id"))
    lote_insumo = db.relationship(LoteInsumo)
    lote = db.relationship("Lote")


class Expedicao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.ForeignKey("lote.id"), nullable=False)
    cliente_id = db.Column(db.ForeignKey("cliente.id"), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, nullable=False, default=datetime.now)
    lote = db.relationship("Lote", back_populates="expedicoes")
    cliente = db.relationship(Cliente)


# --------------------------------------------------------------------------
# Produção
# --------------------------------------------------------------------------
class Formula(db.Model):
    """Fórmula-mestra: insumos por lote e roteiro de fabricação."""
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.ForeignKey("item.id"), nullable=False)
    versao = db.Column(db.String(10), nullable=False)
    rendimento = db.Column(db.Float, nullable=False)  # unidades de produto por lote
    produto = db.relationship(Item)
    itens = db.relationship("ItemFormula", back_populates="formula")
    etapas = db.relationship("EtapaPadrao", back_populates="formula",
                             order_by="EtapaPadrao.ordem")


class ItemFormula(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    formula_id = db.Column(db.ForeignKey("formula.id"), nullable=False)
    item_id = db.Column(db.ForeignKey("item.id"), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    formula = db.relationship(Formula, back_populates="itens")
    item = db.relationship(Item)


class EtapaPadrao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    formula_id = db.Column(db.ForeignKey("formula.id"), nullable=False)
    ordem = db.Column(db.Integer, nullable=False)
    nome = db.Column(db.String(60), nullable=False)
    ciclos_necessarios = db.Column(db.Integer, nullable=False, default=3)
    formula = db.relationship(Formula, back_populates="etapas")
    parametros = db.relationship("ParametroControle", back_populates="etapa_padrao")


class ParametroControle(db.Model):
    """Limites de processo: são dados cadastrados, não código (RNF10)."""
    id = db.Column(db.Integer, primary_key=True)
    etapa_padrao_id = db.Column(db.ForeignKey("etapa_padrao.id"), nullable=False)
    nome = db.Column(db.String(60), nullable=False)
    unidade = db.Column(db.String(10), nullable=False)
    alerta_min = db.Column(db.Float, nullable=False)
    alerta_max = db.Column(db.Float, nullable=False)
    espec_min = db.Column(db.Float, nullable=False)
    espec_max = db.Column(db.Float, nullable=False)
    etapa_padrao = db.relationship(EtapaPadrao, back_populates="parametros")

    def classificar(self, valor):
        """RF06: Conforme, Alerta ou Fora de Especificação."""
        if valor < self.espec_min or valor > self.espec_max:
            return Classificacao.FORA_DE_ESPECIFICACAO
        if valor < self.alerta_min or valor > self.alerta_max:
            return Classificacao.ALERTA
        return Classificacao.CONFORME


class OrdemProducao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    formula_id = db.Column(db.ForeignKey("formula.id"), nullable=False)
    criada_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    criada_por = db.Column(db.String(80), nullable=False)
    formula = db.relationship(Formula)
    lote = db.relationship("Lote", back_populates="ordem", uselist=False)


class Lote(db.Model):
    """Lote de produto: elemento central da rastreabilidade."""
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    ordem_id = db.Column(db.ForeignKey("ordem_producao.id"), nullable=False)
    status = db.Column(db.Enum(StatusLote), nullable=False,
                       default=StatusLote.PLANEJADO)
    quantidade_produzida = db.Column(db.Float, nullable=False, default=0)
    saldo = db.Column(db.Float, nullable=False, default=0)
    fabricado_em = db.Column(db.Date)
    validade = db.Column(db.Date)
    ordem = db.relationship(OrdemProducao, back_populates="lote")
    etapas = db.relationship("EtapaProducao", back_populates="lote",
                             order_by="EtapaProducao.id")
    consumos = db.relationship("ConsumoInsumo", back_populates="lote")
    intervencoes = db.relationship("Intervencao", back_populates="lote",
                                   order_by="Intervencao.id")
    analises = db.relationship("AnaliseQualidade", back_populates="lote")
    expedicoes = db.relationship(Expedicao, back_populates="lote")

    @property
    def produto(self):
        return self.ordem.formula.produto

    @property
    def etapa_atual(self):
        for etapa in self.etapas:
            if etapa.status == StatusEtapa.EM_EXECUCAO:
                return etapa
        return None


class EtapaProducao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.ForeignKey("lote.id"), nullable=False)
    etapa_padrao_id = db.Column(db.ForeignKey("etapa_padrao.id"), nullable=False)
    status = db.Column(db.Enum(StatusEtapa), nullable=False,
                       default=StatusEtapa.PENDENTE)
    ciclos = db.Column(db.Integer, nullable=False, default=0)
    reprocessos = db.Column(db.Integer, nullable=False, default=0)
    iniciada_em = db.Column(db.DateTime)
    concluida_em = db.Column(db.DateTime)
    lote = db.relationship(Lote, back_populates="etapas")
    etapa_padrao = db.relationship(EtapaPadrao)
    leituras = db.relationship("Leitura", back_populates="etapa",
                               order_by="Leitura.id")


class Leitura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    etapa_id = db.Column(db.ForeignKey("etapa_producao.id"), nullable=False)
    parametro_id = db.Column(db.ForeignKey("parametro_controle.id"), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    classificacao = db.Column(db.Enum(Classificacao), nullable=False)
    registrada_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    etapa = db.relationship(EtapaProducao, back_populates="leituras")
    parametro = db.relationship(ParametroControle)


class Intervencao(db.Model):
    """Ponto em que o sistema para e aguarda uma decisão humana."""
    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.ForeignKey("lote.id"), nullable=False)
    tipo = db.Column(db.Enum(TipoIntervencao), nullable=False)
    motivo = db.Column(db.String(300), nullable=False)
    status = db.Column(db.Enum(StatusIntervencao), nullable=False,
                       default=StatusIntervencao.ABERTA)
    aberta_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    leitura_id = db.Column(db.ForeignKey("leitura.id"))
    decisao = db.Column(db.Enum(Decisao))
    justificativa = db.Column(db.String(300))
    resolvida_por = db.Column(db.String(80))
    resolvida_em = db.Column(db.DateTime)
    lote = db.relationship(Lote, back_populates="intervencoes")
    leitura = db.relationship(Leitura)

    @property
    def pendente(self):
        return self.status != StatusIntervencao.RESOLVIDA


class ConsumoInsumo(db.Model):
    """Genealogia: quanto de cada lote de insumo entrou no lote (RN10)."""
    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.ForeignKey("lote.id"), nullable=False)
    lote_insumo_id = db.Column(db.ForeignKey("lote_insumo.id"), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    lote = db.relationship(Lote, back_populates="consumos")
    lote_insumo = db.relationship(LoteInsumo, backref="consumos")


# --------------------------------------------------------------------------
# Qualidade
# --------------------------------------------------------------------------
class AnaliseQualidade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.ForeignKey("lote.id"))
    lote_insumo_id = db.Column(db.ForeignKey("lote_insumo.id"))
    resultado = db.Column(db.Enum(Resultado), nullable=False)
    observacao = db.Column(db.String(300), nullable=False)
    analista = db.Column(db.String(80), nullable=False)
    assinada_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    lote = db.relationship(Lote, back_populates="analises")
    lote_insumo = db.relationship(LoteInsumo)


recall_lotes = db.Table(
    "recall_lotes",
    db.Column("recall_id", db.ForeignKey("recall.id"), primary_key=True),
    db.Column("lote_id", db.ForeignKey("lote.id"), primary_key=True),
)


class Recall(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    motivo = db.Column(db.String(300), nullable=False)
    origem_lote_insumo_id = db.Column(db.ForeignKey("lote_insumo.id"))
    origem_lote_id = db.Column(db.ForeignKey("lote.id"))
    iniciado_por = db.Column(db.String(80), nullable=False)
    iniciado_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    origem_lote_insumo = db.relationship(LoteInsumo)
    origem_lote = db.relationship(Lote, foreign_keys=[origem_lote_id])
    lotes_afetados = db.relationship(Lote, secondary=recall_lotes)
