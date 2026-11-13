"""Serviço de Produção: o motor autônomo da linha.

Princípio da autonomia assimétrica (RN06): o motor pausa, bloqueia e alerta
sozinho, mas nunca retoma a linha depois de um desvio sem decisão humana.
"""
import random
from datetime import date, datetime, timedelta

from ..models import (Alerta, Classificacao, Decisao, EtapaProducao, Intervencao,
                      Leitura, Lote, OrdemProducao, Perfil, StatusEtapa,
                      StatusIntervencao, StatusLote, TipoIntervencao, db)
from ..formato import numero
from . import auditoria, estoque
from .auditoria import SISTEMA, RegraDeNegocio

PRAZO_INTERVENCAO = timedelta(minutes=15)  # RN14


# ----------------------------------------------------------- ordem de produção
def criar_ordem(usuario, formula):
    """RF01: a pessoa cria a ordem; o sistema gera o lote com código único."""
    auditoria.exigir_perfil(usuario, Perfil.PLANEJADOR)
    sequencia = OrdemProducao.query.count() + 1
    ordem = OrdemProducao(numero=f"OP-{date.today().year}-{sequencia:03d}",
                          formula=formula, criada_por=usuario.login)
    lote = Lote(codigo=f"LP-{date.today().year}-{sequencia:03d}", ordem=ordem,
                status=StatusLote.PLANEJADO)
    for padrao in formula.etapas:
        lote.etapas.append(EtapaProducao(etapa_padrao=padrao))
    db.session.add_all([ordem, lote])
    db.session.flush()
    auditoria.registrar(usuario.login, "CRIAR_ORDEM", ordem.numero,
                        f"lote {lote.codigo} de {formula.produto.nome}")
    return ordem


def iniciar_ordem(lote, hoje=None):
    """RF02 a RF05: verifica o estoque, baixa por FEFO e inicia a primeira etapa.

    Executado na mesma transação da mudança de estado do lote (RNF07).
    """
    if lote.status not in (StatusLote.PLANEJADO, StatusLote.AGUARDANDO_MATERIAL):
        raise RegraDeNegocio(f"O lote {lote.codigo} já foi iniciado.")
    faltas = estoque.verificar_disponibilidade(lote.ordem.formula, hoje)
    if faltas:
        _suspender_por_falta(lote, faltas)
        return False
    estoque.baixar_insumos_fefo(lote, hoje)
    for intervencao in lote.intervencoes:  # falta de material resolvida
        if intervencao.pendente and intervencao.tipo == TipoIntervencao.FALTA_MATERIAL:
            _fechar(intervencao, SISTEMA, Decisao.MATERIAL_DISPONIVEL,
                    "Insumo aprovado disponível no estoque.")
    lote.status = StatusLote.EM_PRODUCAO
    _iniciar_etapa(lote.etapas[0])
    auditoria.registrar(SISTEMA, "INICIAR_PRODUCAO", lote.codigo,
                        "insumos baixados; linha em execução")
    return True


def _suspender_por_falta(lote, faltas):
    """RF04: sem insumo aprovado, o lote aguarda e o almoxarifado é avisado."""
    motivo = "; ".join(f"faltam {numero(q)} {item.unidade} de {item.nome}" for item, q in faltas)
    if lote.status == StatusLote.AGUARDANDO_MATERIAL:
        return
    lote.status = StatusLote.AGUARDANDO_MATERIAL
    db.session.add(Intervencao(lote=lote, tipo=TipoIntervencao.FALTA_MATERIAL,
                               motivo=motivo))
    auditoria.registrar(SISTEMA, "SUSPENDER_POR_FALTA", lote.codigo, motivo)


def _iniciar_etapa(etapa):
    etapa.status = StatusEtapa.EM_EXECUCAO
    etapa.iniciada_em = etapa.iniciada_em or datetime.now()
    etapa.ciclos = 0


# ------------------------------------------------------------------- leituras
def processar_leitura(lote, parametro, valor):
    """RF06 a RF08: classifica a leitura e reage a ela.

    É o ponto de entrada das leituras, tanto do simulador quanto da API
    (RNF09). A reação a uma leitura fora de especificação ocorre aqui mesmo,
    sem espera (RNF03).
    """
    etapa = lote.etapa_atual
    if lote.status != StatusLote.EM_PRODUCAO or etapa is None:
        raise RegraDeNegocio(f"RN05: a linha do lote {lote.codigo} não está em execução.")
    if parametro.etapa_padrao_id != etapa.etapa_padrao_id:
        raise RegraDeNegocio("RN04: o parâmetro não pertence à etapa em execução.")
    leitura = Leitura(etapa=etapa, parametro=parametro, valor=valor,
                      classificacao=parametro.classificar(valor))
    db.session.add(leitura)
    db.session.flush()
    texto = f"{parametro.nome} = {numero(valor)} {parametro.unidade} na etapa {etapa.etapa_padrao.nome}"
    if leitura.classificacao == Classificacao.ALERTA:  # RF07: registra e segue
        db.session.add(Alerta(tipo="ALERTA_PROCESSO", mensagem=f"{lote.codigo}: {texto}"))
    elif leitura.classificacao == Classificacao.FORA_DE_ESPECIFICACAO:  # RF08: para
        _pausar_linha(lote, leitura, texto)
    return leitura


def _pausar_linha(lote, leitura, texto):
    """RN05: pausa imediata. Daqui em diante só uma pessoa decide (RF09)."""
    p = leitura.parametro
    lote.status = StatusLote.AGUARDANDO_INTERVENCAO
    motivo = f"{texto} (especificação: {numero(p.espec_min)} a {numero(p.espec_max)} {p.unidade})"
    db.session.add(Intervencao(lote=lote, tipo=TipoIntervencao.DESVIO_PROCESSO,
                               motivo=motivo, leitura=leitura))
    auditoria.registrar(SISTEMA, "PAUSAR_LINHA", lote.codigo, motivo)


def concluir_ciclo(lote):
    """RF05 e RF11: fecha um ciclo de leituras e avança quando a etapa termina."""
    etapa = lote.etapa_atual
    if lote.status != StatusLote.EM_PRODUCAO or etapa is None:
        return
    etapa.ciclos += 1
    if etapa.ciclos < etapa.etapa_padrao.ciclos_necessarios:
        return
    etapa.status = StatusEtapa.CONCLUIDA
    etapa.concluida_em = datetime.now()
    auditoria.registrar(SISTEMA, "CONCLUIR_ETAPA", lote.codigo, etapa.etapa_padrao.nome)
    pendentes = [e for e in lote.etapas if e.status == StatusEtapa.PENDENTE]
    if pendentes:
        _iniciar_etapa(pendentes[0])  # RN04: só agora a próxima começa
    else:
        _enviar_para_quarentena(lote)


def _enviar_para_quarentena(lote):
    """RF11: lote concluído fica bloqueado até a decisão do CQ."""
    formula = lote.ordem.formula
    hoje = date.today()
    lote.status = StatusLote.EM_QUARENTENA
    lote.quantidade_produzida = formula.rendimento
    lote.fabricado_em = hoje
    lote.validade = hoje + timedelta(days=30 * formula.produto.validade_meses)
    auditoria.registrar(SISTEMA, "ENVIAR_PARA_QUARENTENA", lote.codigo,
                        "fabricação concluída; aguardando Controle de Qualidade")


# --------------------------------------------------------------- intervenções
def resolver_intervencao(usuario, intervencao, decisao, senha, justificativa):
    """RF09: somente o Supervisor decide um desvio, com assinatura (RN06, RN07)."""
    auditoria.exigir_perfil(usuario, Perfil.SUPERVISOR)
    if intervencao.tipo != TipoIntervencao.DESVIO_PROCESSO or not intervencao.pendente:
        raise RegraDeNegocio("Esta intervenção não está aguardando decisão de desvio.")
    if decisao not in (Decisao.RETOMAR, Decisao.REPROCESSAR, Decisao.SEGREGAR):
        raise RegraDeNegocio("Decisão inválida para um desvio de processo.")
    auditoria.exigir_assinatura(usuario, senha, justificativa)
    lote, etapa = intervencao.lote, intervencao.lote.etapa_atual
    if decisao == Decisao.RETOMAR:
        lote.status = StatusLote.EM_PRODUCAO
    elif decisao == Decisao.REPROCESSAR:
        etapa.ciclos = 0
        etapa.reprocessos += 1
        lote.status = StatusLote.EM_PRODUCAO
    else:
        etapa.status = StatusEtapa.INTERROMPIDA
        lote.status = StatusLote.REPROVADO
    _fechar(intervencao, usuario.login, decisao, justificativa)
    return intervencao


def _fechar(intervencao, autor, decisao, justificativa):
    intervencao.status = StatusIntervencao.RESOLVIDA
    intervencao.decisao = decisao
    intervencao.justificativa = justificativa
    intervencao.resolvida_por = autor
    intervencao.resolvida_em = datetime.now()
    auditoria.registrar(autor, "RESOLVER_INTERVENCAO", intervencao.lote.codigo,
                        f"{decisao.value}: {justificativa}")


def verificar_prazos(agora=None):
    """RF10 e RN14: intervenção sem resposta em 15 minutos sobe para a gerência."""
    agora = agora or datetime.now()
    escalonadas = []
    for i in Intervencao.query.filter_by(status=StatusIntervencao.ABERTA,
                                         tipo=TipoIntervencao.DESVIO_PROCESSO).all():
        if agora - i.aberta_em >= PRAZO_INTERVENCAO:
            i.status = StatusIntervencao.ESCALONADA
            escalonadas.append(i)
            auditoria.registrar(SISTEMA, "ESCALONAR_INTERVENCAO", i.lote.codigo,
                                "sem resposta no prazo; Gerente da Qualidade notificado")
    return escalonadas


def intervencoes_pendentes():
    return (Intervencao.query.filter(Intervencao.status != StatusIntervencao.RESOLVIDA)
            .order_by(Intervencao.aberta_em).all())


# ----------------------------------------------------------------- simulador
class SimuladorDeSensores:
    """Substitui os sensores da linha no protótipo.

    Em produção, as leituras chegariam do sistema supervisório pela API
    (POST /api/leituras). Aqui elas são sorteadas dentro da faixa de alerta,
    a menos que uma anomalia tenha sido injetada pela tela.
    """
    anomalia_pendente = False

    def __init__(self, semente=None):
        self._sorteio = random.Random(semente)

    def gerar(self, parametro):
        centro = (parametro.alerta_min + parametro.alerta_max) / 2
        folga = (parametro.alerta_max - parametro.alerta_min) / 2
        if SimuladorDeSensores.anomalia_pendente:
            SimuladorDeSensores.anomalia_pendente = False
            excesso = (parametro.espec_max - parametro.espec_min) * 0.15
            return round(parametro.espec_max + excesso, 2)
        return round(centro + self._sorteio.uniform(-0.8, 0.8) * folga, 2)


def executar_ciclo(simulador=None, hoje=None, agora=None):
    """Um ciclo do motor autônomo. Nenhuma pessoa participa deste método."""
    simulador = simulador or SimuladorDeSensores()
    for lote in Lote.query.filter_by(status=StatusLote.AGUARDANDO_MATERIAL).all():
        iniciar_ordem(lote, hoje)  # retoma sozinho quando o insumo aprovado chega
    for lote in Lote.query.filter_by(status=StatusLote.EM_PRODUCAO).all():
        for parametro in lote.etapa_atual.etapa_padrao.parametros:
            leitura = processar_leitura(lote, parametro, simulador.gerar(parametro))
            if leitura.classificacao == Classificacao.FORA_DE_ESPECIFICACAO:
                break
        concluir_ciclo(lote)  # não faz nada se a linha foi pausada
    verificar_prazos(agora)
    estoque.rotina_validade(hoje)
    db.session.commit()
