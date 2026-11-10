"""
Sistema Integrado para a Industria Farmaceutica
Implementacao de referencia das classes do dominio (Diagrama de Classes, Secao 5.2
do Relatorio Final).

Escopo desta implementacao: apenas a camada de modelo/negocio (classes, atributos,
relacionamentos e regras de negocio RN01-RN07 do Documento de Requisitos). Nao ha
interface grafica, API ou banco de dados — o foco e demonstrar que a modelagem UML
se traduz em um codigo orientado a objetos consistente.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional


# ---------------------------------------------------------------------------
# Enumeracoes (equivalentes as <<enumeration>> do Diagrama de Classes)
# ---------------------------------------------------------------------------

class StatusOrdem(Enum):
    ABERTA = "aberta"
    EM_ANDAMENTO = "em_andamento"
    CONCLUIDA = "concluida"


class StatusLote(Enum):
    EM_PRODUCAO = "em_producao"
    EM_INSPECAO = "em_inspecao"
    APROVADO = "aprovado"
    REPROVADO = "reprovado"
    DISPONIVEL = "disponivel"
    ESGOTADO = "esgotado"


class ResultadoInspecao(Enum):
    CONFORME = "conforme"
    NAO_CONFORME = "nao_conforme"


# ---------------------------------------------------------------------------
# Usuarios (hierarquia Usuario <|-- ...)
# ---------------------------------------------------------------------------

@dataclass
class Usuario:
    id: int
    nome: str
    login: str


@dataclass
class OperadorProducao(Usuario):
    pass


@dataclass
class AnalistaQualidade(Usuario):
    pass


@dataclass
class AnalistaEstoque(Usuario):
    pass


@dataclass
class Gerente(Usuario):
    pass


# ---------------------------------------------------------------------------
# Modulo de Producao
# ---------------------------------------------------------------------------

@dataclass
class MateriaPrima:
    codigo: str
    nome: str
    fornecedor: str
    data_validade_insumo: date

    def validade_vigente(self, referencia: date) -> bool:
        """RN07 — materia-prima sem validade vigente nao pode ser usada em producao."""
        return self.data_validade_insumo >= referencia


@dataclass
class ConsumoInsumo:
    materia_prima: MateriaPrima
    quantidade_utilizada: float


@dataclass
class OrdemProducao:
    id: int
    produto: str
    quantidade_planejada: int
    data_inicio_prevista: date
    data_fim_prevista: date
    status: StatusOrdem = StatusOrdem.ABERTA
    lotes: List["Lote"] = field(default_factory=list)

    def registrar_lote(self, lote: "Lote") -> None:
        """RF01/RF02 — associa um lote recem-criado a esta ordem de producao."""
        self.lotes.append(lote)
        lote.ordem_producao = self
        self.status = StatusOrdem.EM_ANDAMENTO


@dataclass
class Lote:
    numero_lote: str
    data_fabricacao: date
    data_validade: date
    quantidade_produzida: int
    status: StatusLote = StatusLote.EM_PRODUCAO
    ordem_producao: Optional[OrdemProducao] = None
    consumos: List[ConsumoInsumo] = field(default_factory=list)
    inspecoes: List["InspecaoQualidade"] = field(default_factory=list)

    def registrar_consumo(self, consumo: ConsumoInsumo, referencia: date) -> None:
        """RF03, aplicando a RN07 (materia-prima vencida nao pode ser consumida)."""
        if not consumo.materia_prima.validade_vigente(referencia):
            codigo = consumo.materia_prima.codigo
            raise ValueError(f"Materia-prima {codigo} fora da validade (RN07).")
        self.consumos.append(consumo)

    def solicitar_inspecao(self) -> None:
        """RF05 — Operador de Producao solicita inspecao de qualidade do lote."""
        self.status = StatusLote.EM_INSPECAO

    def aplicar_resultado_inspecao(self, inspecao: "InspecaoQualidade") -> None:
        """Efeito de RF06: aprova ou reprova o lote conforme o resultado da inspecao."""
        self.inspecoes.append(inspecao)
        if inspecao.resultado == ResultadoInspecao.CONFORME:
            self.status = StatusLote.APROVADO
        else:
            # RN02 — estado terminal: um lote reprovado nunca vai a estoque.
            self.status = StatusLote.REPROVADO

    def liberar_para_estoque(self) -> "ItemEstoque":
        """RF11, aplicando a RN01 — so libera lote aprovado pela Qualidade."""
        if self.status != StatusLote.APROVADO:
            raise ValueError(
                f"Lote {self.numero_lote} nao pode ser liberado para estoque: "
                f"status atual e '{self.status.value}' (RN01)."
            )
        self.status = StatusLote.DISPONIVEL
        return ItemEstoque(
            lote=self,
            quantidade_disponivel=self.quantidade_produzida,
            localizacao="A definir",
        )


# ---------------------------------------------------------------------------
# Modulo de Qualidade
# ---------------------------------------------------------------------------

@dataclass
class LaudoQualidade:
    numero_laudo: str
    parecer: str
    data_emissao: date


@dataclass
class InspecaoQualidade:
    id: int
    lote: Lote
    data_inspecao: date
    resultado: Optional[ResultadoInspecao] = None
    observacoes: str = ""
    laudo: Optional[LaudoQualidade] = None

    def registrar_resultado(
        self, resultado: ResultadoInspecao, observacoes: str = ""
    ) -> None:
        """RF06 — Analista de Qualidade registra o resultado da inspecao."""
        self.resultado = resultado
        self.observacoes = observacoes
        self.lote.aplicar_resultado_inspecao(self)
        if resultado == ResultadoInspecao.CONFORME:
            self.emitir_laudo()

    def emitir_laudo(self) -> LaudoQualidade:
        """RF07 — emissao de laudo de qualidade para lotes aprovados."""
        self.laudo = LaudoQualidade(
            numero_laudo=f"LQ-{self.lote.numero_lote}",
            parecer="Aprovado",
            data_emissao=self.data_inspecao,
        )
        return self.laudo


# ---------------------------------------------------------------------------
# Modulo de Estoque e Logistica
# ---------------------------------------------------------------------------

@dataclass
class AlertaValidade:
    data_alerta: date
    dias_restantes: int


@dataclass
class ItemEstoque:
    lote: Lote
    quantidade_disponivel: int
    localizacao: str
    alertas: List[AlertaValidade] = field(default_factory=list)

    def verificar_validade(
        self, referencia: date, dias_antecedencia: int = 30
    ) -> Optional[AlertaValidade]:
        """RF14 / RN04 — emite alerta quando a validade esta proxima (FEFO)."""
        dias_restantes = (self.lote.data_validade - referencia).days
        if 0 <= dias_restantes <= dias_antecedencia:
            alerta = AlertaValidade(data_alerta=referencia, dias_restantes=dias_restantes)
            self.alertas.append(alerta)
            return alerta
        return None

    def consumir(self, quantidade: int) -> None:
        """RF13 — baixa de produtos acabados; esgota o lote quando chega a zero."""
        if quantidade > self.quantidade_disponivel:
            raise ValueError("Quantidade solicitada maior que a disponivel em estoque.")
        self.quantidade_disponivel -= quantidade
        if self.quantidade_disponivel == 0:
            self.lote.status = StatusLote.ESGOTADO


# ---------------------------------------------------------------------------
# Demonstracao do fluxo completo (equivalente ao Diagrama de Sequencia, Secao 5.4)
# ---------------------------------------------------------------------------

def demonstracao() -> None:
    materia_prima = MateriaPrima(
        codigo="MP-001",
        nome="Paracetamol (principio ativo)",
        fornecedor="Fornecedor A",
        data_validade_insumo=date(2027, 6, 1),
    )

    ordem = OrdemProducao(
        id=1,
        produto="Analgesico 500mg",
        quantidade_planejada=10000,
        data_inicio_prevista=date(2026, 11, 1),
        data_fim_prevista=date(2026, 11, 5),
    )

    lote = Lote(
        numero_lote="L2026-0001",
        data_fabricacao=date(2026, 11, 5),
        data_validade=date(2027, 11, 5),
        quantidade_produzida=10000,
    )
    ordem.registrar_lote(lote)
    lote.registrar_consumo(
        ConsumoInsumo(materia_prima=materia_prima, quantidade_utilizada=50.0),
        referencia=date(2026, 11, 5),
    )

    # Operador solicita inspecao (RF05)
    lote.solicitar_inspecao()
    print(f"Status do lote apos solicitar inspecao: {lote.status.value}")

    # Analista de Qualidade inspeciona e aprova o lote (RF06/RF07)
    inspecao = InspecaoQualidade(id=1, lote=lote, data_inspecao=date(2026, 11, 6))
    inspecao.registrar_resultado(
        ResultadoInspecao.CONFORME, "Dentro das especificacoes."
    )
    print(f"Status do lote apos inspecao: {lote.status.value}")
    print(f"Laudo emitido: {inspecao.laudo.numero_laudo} ({inspecao.laudo.parecer})")

    # Analista de Estoque libera o lote aprovado (RF11, RN01)
    item_estoque = lote.liberar_para_estoque()
    print(f"Status do lote apos liberar estoque: {lote.status.value}")
    qtd, local = item_estoque.quantidade_disponivel, item_estoque.localizacao
    print(f"Item em estoque: {qtd} unidades em '{local}'")

    # Tentativa de liberar um segundo lote reprovado, para mostrar a RN01 em acao
    lote_reprovado = Lote(
        numero_lote="L2026-0002",
        data_fabricacao=date(2026, 11, 5),
        data_validade=date(2027, 11, 5),
        quantidade_produzida=5000,
    )
    inspecao_2 = InspecaoQualidade(
        id=2, lote=lote_reprovado, data_inspecao=date(2026, 11, 6)
    )
    inspecao_2.registrar_resultado(
        ResultadoInspecao.NAO_CONFORME, "Desvio no teor do principio ativo."
    )
    try:
        lote_reprovado.liberar_para_estoque()
    except ValueError as erro:
        print(f"Bloqueio esperado (RN01): {erro}")


if __name__ == "__main__":
    demonstracao()
