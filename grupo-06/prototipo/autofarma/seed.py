"""Carga inicial do cenário de estudo: Aurora Farmacêutica (fictícia),
linha de sólidos orais, Paracetamol 500 mg comprimidos.

Os valores de fórmula e de limites de processo são ilustrativos.
"""
from datetime import date, timedelta

from .models import (Cliente, EtapaPadrao, Formula, ItemFormula, LoteInsumo,
                     MateriaPrima, MaterialEmbalagem, ParametroControle, Perfil,
                     ProdutoAcabado, StatusEstoque, Usuario, db)
from .servicos import auditoria

SENHA_DEMO = "1234"

USUARIOS = [
    ("Ana Prado", "planejador", Perfil.PLANEJADOR),
    ("Bruno Sato", "supervisor", Perfil.SUPERVISOR),
    ("Carla Reis", "analista", Perfil.ANALISTA_CQ),
    ("Diego Lima", "almoxarife", Perfil.ALMOXARIFE),
    ("Elisa Mota", "gerente", Perfil.GERENTE_QUALIDADE),
]

# etapa, ciclos, [(parâmetro, unidade, alerta_min, alerta_max, espec_min, espec_max)]
ROTEIRO = [
    ("Pesagem", [("Desvio de pesagem", "%", -0.30, 0.30, -0.50, 0.50)]),
    ("Mistura", [("Velocidade do misturador", "rpm", 19, 21, 18, 22)]),
    ("Granulação e secagem", [("Umidade do granulado", "%", 1.3, 2.7, 1.0, 3.0)]),
    ("Compressão", [("Peso médio do comprimido", "mg", 585, 615, 570, 630),
                    ("Dureza do comprimido", "kgf", 7, 11, 6, 12)]),
    ("Embalagem", [("Temperatura de selagem do blíster", "°C", 145, 155, 140, 160)]),
]


def popular(hoje=None):
    hoje = hoje or date.today()
    for nome, login, perfil in USUARIOS:
        usuario = Usuario(nome=nome, login=login, perfil=perfil)
        usuario.definir_senha(SENHA_DEMO)
        db.session.add(usuario)

    mp = {
        "paracetamol": MateriaPrima(codigo="MP-001", nome="Paracetamol", unidade="kg", estoque_minimo=100),
        "amido": MateriaPrima(codigo="MP-002", nome="Amido de milho", unidade="kg", estoque_minimo=10),
        "celulose": MateriaPrima(codigo="MP-003", nome="Celulose microcristalina", unidade="kg", estoque_minimo=6),
        "povidona": MateriaPrima(codigo="MP-004", nome="Povidona K30", unidade="kg", estoque_minimo=3),
        "estearato": MateriaPrima(codigo="MP-005", nome="Estearato de magnésio", unidade="kg", estoque_minimo=1),
        "blister": MaterialEmbalagem(codigo="EM-001", nome="Blíster PVC/alumínio", unidade="un", estoque_minimo=20000),
        "cartucho": MaterialEmbalagem(codigo="EM-002", nome="Cartucho", unidade="un", estoque_minimo=10000),
    }
    produto = ProdutoAcabado(codigo="PA-001", unidade="cx", validade_meses=24,
                             nome="Paracetamol 500 mg, caixa com 20 comprimidos")
    db.session.add_all([*mp.values(), produto])

    # Lote padrão: 100 kg de mistura = 8.300 caixas de 20 comprimidos de 600 mg.
    formula = Formula(produto=produto, versao="1.0", rendimento=8300)
    for chave, quantidade in [("paracetamol", 83.3), ("amido", 9.0), ("celulose", 5.0),
                              ("povidona", 2.0), ("estearato", 0.7),
                              ("blister", 16600), ("cartucho", 8300)]:
        formula.itens.append(ItemFormula(item=mp[chave], quantidade=quantidade))
    for ordem, (nome, parametros) in enumerate(ROTEIRO, start=1):
        etapa = EtapaPadrao(ordem=ordem, nome=nome, ciclos_necessarios=3)
        for p in parametros:
            etapa.parametros.append(ParametroControle(
                nome=p[0], unidade=p[1], alerta_min=p[2], alerta_max=p[3],
                espec_min=p[4], espec_max=p[5]))
        formula.etapas.append(etapa)
    db.session.add(formula)

    A, Q = StatusEstoque.APROVADO, StatusEstoque.QUARENTENA
    estoque_inicial = [
        # item, fornecedor, lote do fornecedor, validade (dias), quantidade, status
        ("paracetamol", "Química Vale", "QV-8841", 45, 60, A),     # vence antes: sai primeiro (FEFO)
        ("paracetamol", "Química Vale", "QV-9012", 400, 150, A),
        ("paracetamol", "Insumos Atlas", "AT-2207", 500, 100, Q),  # ainda em quarentena
        ("amido", "Amidos do Sul", "AS-0457", 300, 40, A),
        ("amido", "Amidos do Sul", "AS-0391", -10, 5, A),          # vencido: será bloqueado
        ("celulose", "Insumos Atlas", "AT-2198", 350, 25, A),
        ("povidona", "Insumos Atlas", "AT-2201", 280, 10, A),
        ("estearato", "Química Vale", "QV-8790", 200, 1.0, A),     # dá para um lote só
        ("estearato", "Química Vale", "QV-9050", 420, 5.0, Q),
        ("blister", "Embalagens Tietê", "ET-3310", 700, 50000, A),
        ("cartucho", "Embalagens Tietê", "ET-3322", 700, 25000, A),
    ]
    for n, (chave, fornecedor, lf, dias, qtd, status) in enumerate(estoque_inicial, start=1):
        db.session.add(LoteInsumo(
            codigo=f"LI-{hoje.year}-{n:03d}", item=mp[chave], fornecedor=fornecedor,
            lote_fornecedor=lf, validade=hoje + timedelta(days=dias),
            quantidade_recebida=qtd, saldo=qtd, status=status))

    db.session.add_all([
        Cliente(nome="Drogaria Central", cidade="Barueri"),
        Cliente(nome="Hospital Santa Clara", cidade="Osasco"),
        Cliente(nome="Distribuidora Vida", cidade="São Paulo"),
    ])
    db.session.flush()
    auditoria.registrar(auditoria.SISTEMA, "CARGA_INICIAL", "cenário",
                        "usuários, fórmula, roteiro e estoque inicial do cenário de estudo")
    db.session.commit()
