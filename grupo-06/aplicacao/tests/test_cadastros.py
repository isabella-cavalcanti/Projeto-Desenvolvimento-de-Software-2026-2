"""Testes dos cadastros, dos indicadores e da segurança de acesso."""
import pytest

from autofarma import create_app
from autofarma.models import (Formula, Item, ParametroControle, Perfil, RegistroAuditoria,
                              StatusLote, Usuario, db)
from autofarma.seed import SENHA_DEMO
from autofarma.servicos import cadastros, indicadores, producao
from autofarma.servicos.auditoria import RegraDeNegocio

CONFIG = {"SQLALCHEMY_DATABASE_URI": "sqlite://", "TESTING": True, "DEMO": True}


@pytest.fixture
def app():
    app = create_app({**CONFIG, "CSRF_ATIVO": False})
    with app.app_context():
        producao.SimuladorDeSensores.anomalia_pendente = False
        yield app


def usuario(login):
    return Usuario.query.filter_by(login=login).one()


def parametro(nome):
    return ParametroControle.query.filter_by(nome=nome).one()


# ------------------------------------------------------------------- cadastros
def test_rf26_almoxarife_cadastra_insumo_e_codigo_nao_se_repete(app):
    item = cadastros.salvar_item(usuario("almoxarife"), "materia_prima", "MP-006",
                                 "Lactose", "kg", 20)
    assert item.id and item.tipo == "materia_prima"
    with pytest.raises(RegraDeNegocio, match="Já existe"):
        cadastros.salvar_item(usuario("almoxarife"), "embalagem", "MP-006", "Outro", "un", 0)
    with pytest.raises(RegraDeNegocio, match="RN06"):          # produto acabado é da Qualidade
        cadastros.salvar_item(usuario("almoxarife"), "produto_acabado", "PA-002",
                              "Ibuprofeno 400 mg", "cx", 0, validade_meses=24)


def test_rf27_limite_de_processo_muda_com_assinatura_e_gera_versao(app):
    umidade, gerente = parametro("Umidade do granulado"), usuario("gerente")
    argumentos = (umidade.etapa_padrao, umidade.nome, umidade.unidade, 1.4, 2.6, 1.0, 2.8)
    with pytest.raises(RegraDeNegocio, match="RN06"):          # supervisor não altera limite
        cadastros.salvar_parametro(usuario("supervisor"), *argumentos, SENHA_DEMO, "x",
                                   parametro=umidade)
    with pytest.raises(RegraDeNegocio, match="RN07"):          # sem assinatura válida
        cadastros.salvar_parametro(gerente, *argumentos, "errada", "Revisão", parametro=umidade)
    cadastros.salvar_parametro(gerente, *argumentos, SENHA_DEMO,
                               "Revisão anual de especificação.", parametro=umidade)
    assert umidade.espec_max == 2.8
    assert Formula.query.one().versao == "1.1"
    registro = RegistroAuditoria.query.filter_by(acao="ALTERAR_LIMITE").one()
    assert "antes 1 a 3 %" in registro.detalhe and registro.autor == "gerente"


def test_rn15_faixa_de_alerta_fica_dentro_da_especificacao(app):
    umidade = parametro("Umidade do granulado")
    with pytest.raises(RegraDeNegocio, match="RN15"):
        cadastros.salvar_parametro(usuario("gerente"), umidade.etapa_padrao, umidade.nome, "%",
                                   0.5, 2.7, 1.0, 3.0, SENHA_DEMO, "teste", parametro=umidade)


def test_rn16_formula_nao_muda_com_lote_na_linha(app):
    ordem = producao.criar_ordem(usuario("planejador"), Formula.query.one())
    producao.iniciar_ordem(ordem.lote)
    assert ordem.lote.status == StatusLote.EM_PRODUCAO
    umidade = parametro("Umidade do granulado")
    with pytest.raises(RegraDeNegocio, match="RN16"):
        cadastros.salvar_parametro(usuario("gerente"), umidade.etapa_padrao, umidade.nome, "%",
                                   1.3, 2.7, 1.0, 3.2, SENHA_DEMO, "teste", parametro=umidade)


def test_rf27_nova_formula_so_aceita_ordem_quando_completa(app):
    gerente = usuario("gerente")
    produto = cadastros.salvar_item(gerente, "produto_acabado", "PA-002", "Ibuprofeno 400 mg",
                                    "cx", 0, validade_meses=24)
    formula = cadastros.criar_formula(gerente, produto, 5000, SENHA_DEMO, "Novo produto.")
    assert not cadastros.formula_pronta(formula)
    amido = Item.query.filter_by(codigo="MP-002").one()
    cadastros.definir_item_da_formula(gerente, formula, amido, 10, SENHA_DEMO, "Composição.")
    etapa = cadastros.adicionar_etapa(gerente, formula, "Mistura", 2, SENHA_DEMO, "Roteiro.")
    cadastros.salvar_parametro(gerente, etapa, "Velocidade", "rpm", 19, 21, 18, 22,
                               SENHA_DEMO, "Limites.")
    db.session.commit()
    assert cadastros.formula_pronta(formula)
    ordem = producao.criar_ordem(usuario("planejador"), formula)   # e a linha roda com ela
    producao.iniciar_ordem(ordem.lote)
    for _ in range(4):
        producao.executar_ciclo(producao.SimuladorDeSensores(semente=1))
    assert ordem.lote.status == StatusLote.EM_QUARENTENA


# -------------------------------------------------------------------- usuários
def test_rf28_e_rn17_so_o_administrador_gerencia_e_usuario_inativo_nao_entra(app):
    admin = usuario("admin")
    with pytest.raises(RegraDeNegocio, match="RN06"):
        cadastros.criar_usuario(usuario("gerente"), "X", "x", Perfil.SUPERVISOR, "senha-longa")
    with pytest.raises(RegraDeNegocio, match="RNF01"):         # senha curta
        cadastros.criar_usuario(admin, "Gil Paz", "gil", Perfil.SUPERVISOR, "1234")
    novo = cadastros.criar_usuario(admin, "Gil Paz", "gil", Perfil.SUPERVISOR, "senha-longa")
    cadastros.alterar_usuario(admin, novo, ativo=False)
    with pytest.raises(RegraDeNegocio, match="RN17"):
        cadastros.alterar_usuario(admin, admin, ativo=False)
    db.session.commit()
    resposta = app.test_client().post("/login", data={"login": "gil", "senha": "senha-longa"})
    assert resposta.status_code == 200 and "inválidos" in resposta.get_data(as_text=True)
    assert Usuario.query.filter_by(login="gil").count() == 1   # desativado, não excluído


# ---------------------------------------------------------------- indicadores
def test_rf29_indicadores_refletem_a_operacao(app):
    ordem = producao.criar_ordem(usuario("planejador"), Formula.query.one())
    producao.iniciar_ordem(ordem.lote)
    producao.processar_leitura(ordem.lote, parametro("Desvio de pesagem"), 0.9)
    producao.resolver_intervencao(usuario("supervisor"), ordem.lote.intervencoes[-1],
                                  producao.Decisao.RETOMAR, SENHA_DEMO, "Conferido.")
    dados = indicadores.calcular()
    assert dados["lotes_total"] == 1 and dados["desvios_total"] == 1
    assert dados["desvios_por_etapa"] == [("Pesagem", 1)]
    assert dados["tempo_medio_resposta"] is not None
    estearato = next(x for x in dados["insumos"] if x["item"].codigo == "MP-005")
    assert estearato["abaixo"]


# ------------------------------------------------------------------- segurança
def test_rnf01_api_exige_chave(app):
    c = app.test_client()
    assert c.post("/api/leituras", json={"lote": "x", "parametro": 1, "valor": 1}).status_code == 401
    assert c.get("/api/linha", headers={"X-API-Key": "errada"}).status_code == 401
    assert c.get("/api/linha", headers={"X-API-Key": "chave-demo"}).status_code == 200


def test_rnf01_formulario_sem_token_e_recusado():
    app = create_app({**CONFIG, "CSRF_ATIVO": True})
    with app.app_context():
        c = app.test_client()
        assert c.post("/login", data={"login": "planejador", "senha": SENHA_DEMO}).status_code == 400
        pagina = c.get("/login").get_data(as_text=True)
        token = pagina.split('name="csrf" value="')[1].split('"')[0]
        resposta = c.post("/login", data={"login": "planejador", "senha": SENHA_DEMO, "csrf": token})
        assert resposta.status_code == 302


def test_rf30_relatorio_do_lote_e_telas_novas_abrem(app):
    c = app.test_client()
    c.post("/login", data={"login": "planejador", "senha": SENHA_DEMO})
    c.post("/ordens", data={"formula": 1})
    for caminho in ("/lotes/LP-%d-001/relatorio" % __import__("datetime").date.today().year,
                    "/indicadores", "/cadastros/itens", "/cadastros/formulas",
                    "/cadastros/formulas/1", "/cadastros/usuarios", "/conta"):
        assert c.get(caminho).status_code == 200, caminho


def test_rnf01_conta_bloqueia_apos_cinco_senhas_erradas(app):
    from datetime import datetime, timedelta
    from autofarma.servicos import auditoria
    alvo = usuario("supervisor")
    for _ in range(5):
        assert not auditoria.autenticar(alvo, "errada")
    assert not auditoria.autenticar(alvo, SENHA_DEMO)               # certa, mas bloqueada
    assert RegistroAuditoria.query.filter_by(acao="BLOQUEAR_LOGIN").count() == 1
    depois = datetime.now() + timedelta(minutes=6)
    assert auditoria.autenticar(alvo, SENHA_DEMO, agora=depois)     # libera após 5 minutos


def test_dados_invalidos_viram_recusa_e_nunca_erro_interno(app):
    c = app.test_client()
    c.post("/login", data={"login": "almoxarife", "senha": SENHA_DEMO})
    ruins = [
        ("/estoque/receber", {"item": 1, "fornecedor": "F", "lote_fornecedor": "L", "validade": "ontem", "quantidade": "10"}),
        ("/estoque/receber", {"item": 1, "fornecedor": "F", "lote_fornecedor": "L", "validade": "2099-01-01", "quantidade": "nan"}),
        ("/estoque/receber", {"item": 1, "fornecedor": "F", "lote_fornecedor": "L", "validade": "2000-01-01", "quantidade": "10"}),
        ("/estoque/receber", {"item": 1, "fornecedor": "F", "lote_fornecedor": "L", "validade": "2099-01-01", "quantidade": "-5"}),
        ("/estoque/receber", {"item": 999}),
        ("/expedicao", {"produto": 8, "cliente": 1, "quantidade": "abc"}),
        ("/expedicao", {"produto": 8, "cliente": 1, "quantidade": "inf"}),
        ("/expedicao", {}),
        ("/intervencoes/999/resolver", {"decisao": "RETOMAR"}),
        ("/qualidade/lote/999", {"resultado": "APROVADO"}),
        ("/qualidade/insumo/3", {"resultado": "TALVEZ", "senha": SENHA_DEMO, "observacao": "x"}),
        ("/cadastros/itens", {"tipo": "materia_prima", "codigo": "X" * 500, "nome": "n", "unidade": "kg"}),
        ("/cadastros/itens", {"tipo": "outro", "codigo": "Z-1", "nome": "n", "unidade": "kg"}),
        ("/cadastros/usuarios", {"nome": "a", "login": "b", "perfil": "REI", "senha": "12345678"}),
        ("/cadastros/etapas/1/parametros", {"nome": "p", "unidade": "u", "alerta_min": "x"}),
        ("/recall", {"insumo": "abc", "senha": "x", "motivo": "m"}),
    ]
    antes = LoteInsumoContagem()
    for caminho, dados in ruins:
        resposta = c.post(caminho, data=dados)
        assert resposta.status_code in (302, 404), (caminho, dados, resposta.status_code)
    assert LoteInsumoContagem() == antes                            # nada foi gravado
    chave = {"X-API-Key": "chave-demo"}
    for corpo in ({"lote": "x", "parametro": 1, "valor": "abc"}, {"valor": float("nan")}, {}, []):
        assert c.post("/api/leituras", headers=chave, json=corpo).status_code == 400
    assert c.post("/api/leituras", headers=chave, data="{isto nao e json").status_code == 400


def LoteInsumoContagem():
    from autofarma.models import LoteInsumo
    return LoteInsumo.query.count()


def test_leitura_nao_numerica_nunca_e_classificada_como_conforme(app):
    ordem = producao.criar_ordem(usuario("planejador"), Formula.query.one())
    producao.iniciar_ordem(ordem.lote)
    with pytest.raises(RegraDeNegocio, match="RF06"):
        producao.processar_leitura(ordem.lote, parametro("Desvio de pesagem"), float("nan"))


def test_cabecalhos_de_seguranca_e_redirecionamento_externo(app):
    c = app.test_client()
    resposta = c.get("/login")
    assert resposta.headers["X-Frame-Options"] == "DENY"
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in resposta.headers["Content-Security-Policy"]
    c.post("/login", data={"login": "planejador", "senha": SENHA_DEMO})
    resposta = c.post("/simulador/ciclo", headers={"Referer": "https://site-malicioso.example/x"})
    assert resposta.headers["Location"].startswith("/")             # não segue o Referer de fora


def test_perfil_errado_nao_executa_nenhuma_operacao_de_outro_perfil(app):
    """Varredura: cada operação crítica é recusada para quem não tem o perfil (RN06)."""
    c = app.test_client()
    c.post("/login", data={"login": "planejador", "senha": SENHA_DEMO})
    tentativas = [
        ("/estoque/receber", {"item": 1, "fornecedor": "F", "lote_fornecedor": "L", "validade": "2099-01-01", "quantidade": "10"}),
        ("/qualidade/insumo/3", {"resultado": "APROVADO", "senha": SENHA_DEMO, "observacao": "ok"}),
        ("/estoque/insumo/5/descartar", {"senha": SENHA_DEMO, "justificativa": "x"}),
        ("/recall", {"insumo": 2, "senha": SENHA_DEMO, "motivo": "x"}),
        ("/cadastros/itens", {"tipo": "materia_prima", "codigo": "MP-900", "nome": "n", "unidade": "kg"}),
        ("/cadastros/usuarios", {"nome": "a", "login": "novo", "perfil": "SUPERVISOR", "senha": "12345678"}),
        ("/cadastros/usuarios/2", {"acao": "desativar"}),
        ("/cadastros/formulas/1/rendimento", {"rendimento": "1", "senha": SENHA_DEMO, "justificativa": "x"}),
        ("/cadastros/etapas/1/parametros", {"parametro": 1, "nome": "p", "unidade": "%", "alerta_min": "-9",
                                            "alerta_max": "9", "espec_min": "-99", "espec_max": "99",
                                            "senha": SENHA_DEMO, "justificativa": "x"}),
    ]
    for caminho, dados in tentativas:
        pagina = c.post(caminho, data=dados, follow_redirects=True).get_data(as_text=True)
        assert "RN06" in pagina, caminho
    assert parametro("Desvio de pesagem").espec_max == 0.5
    assert Usuario.query.filter_by(login="novo").count() == 0 and usuario("supervisor").ativo
