"""Gera dados de demonstração realistas para apresentar o sistema.

Simula ~45 dias de operação: insumos recebidos e aprovados, OPs executadas,
lotes liberados pelo CQ, expedição para 4 pontos e milhares de dispensações
com perfis de demanda diferentes (alta, estável, crescente e baixa), além de
uma tentativa de clonagem e uma de falsificação.
"""
import random
from datetime import date, datetime, timedelta

from . import db, servicos as s

DIAS = 45

# registro, nome, apresentação, insumo ativo, g/caixa, caixas produzidas, caixas expedidas, demanda(dia)->qtd
MEDICAMENTOS = [
    ("1043100010017", "Dipirona Sódica 500 mg", "Caixa c/ 20 comprimidos", "Dipirona sódica", 10.0, 1100, 1050,
     lambda d, r: max(0, round(r.gauss(22, 4)))),
    ("1018300420021", "Losartana Potássica 50 mg", "Caixa c/ 30 comprimidos", "Losartana potássica", 1.5, 900, 700,
     lambda d, r: max(0, round(r.gauss(8, 2)))),
    ("1004300150035", "Amoxicilina 500 mg", "Caixa c/ 21 cápsulas", "Amoxicilina tri-hidratada", 10.5, 480, 460,
     lambda d, r: max(0, round(r.gauss(2 + d * 0.28, 1.5)))),
    ("1057300930041", "Omeprazol 20 mg", "Caixa c/ 28 cápsulas", "Omeprazol", 0.56, 800, 300,
     lambda d, r: r.choice([0, 1, 1, 2])),
    ("1023500670058", "Paracetamol 750 mg", "Caixa c/ 20 comprimidos", "Paracetamol", 15.0, 300, 0,
     lambda d, r: 0),
]

PONTOS = [("Hospital São Lucas", "Hospital", "Barueri"),
          ("Drogaria Central Alphaville", "Drogaria", "Barueri"),
          ("Hospital Municipal de Santana", "Hospital", "Santana de Parnaíba"),
          ("Farmácia Popular Osasco", "Drogaria", "Osasco")]


def carregar(semente=42):
    r = random.Random(semente)
    db.limpar_tudo()
    hoje = date.today()
    inicio = hoje - timedelta(days=DIAS)
    fabricacao = datetime.combine(inicio - timedelta(days=6), datetime.min.time()).replace(hour=9)
    validade_insumo = (hoje + timedelta(days=500)).strftime("%d/%m/%Y")

    pontos = [s.cadastrar_ponto(*p) for p in PONTOS]
    excip = s.cadastrar_insumo("Excipientes (amido/celulose)", "g")
    embal = s.cadastrar_insumo("Embalagem (blíster + cartucho)", "un")
    total_caixas = sum(m[5] for m in MEDICAMENTOS)
    for i, q in [(excip, total_caixas * 3 + 2000), (embal, total_caixas + 1000)]:
        s.aprovar_insumo_lote(s.receber_insumo(i, f"FORN-{i:03d}-A", q, validade_insumo))
    # um lote de insumo esperando análise do CQ
    s.receber_insumo(excip, "FORN-001-B", 5000, validade_insumo)

    meds = []
    for reg, nome, apres, ativo, g, prod, exp, demanda in MEDICAMENTOS:
        mid = s.cadastrar_medicamento(reg, nome, apres, 24)
        ins = s.cadastrar_insumo(ativo, "g")
        s.aprovar_insumo_lote(s.receber_insumo(ins, f"IFA-{ins:03d}", round(g * prod * 1.4, 2), validade_insumo))
        s.definir_formula(mid, ins, g)
        s.definir_formula(mid, excip, 3)
        s.definir_formula(mid, embal, 1)
        meds.append((mid, prod, exp, demanda))

    estoque_ponto = []  # (serial, ponto_id, medicamento_id)
    with db.conectar() as con:
        for mid, prod, exp, demanda in meds:
            op = s._abrir_op(con, mid, prod, "Manual", 5, fabricacao.strftime("%Y-%m-%d %H:%M:%S"))
            numero = s._executar_op(con, op, fabricacao)
            lote_id = con.execute("SELECT id FROM lote WHERE numero=?", (numero,)).fetchone()[0]
            if exp == 0:
                continue  # Paracetamol fica em quarentena para demonstrar o CQ
            s._mudar_status_lote(con, lote_id, s.APROVADO, quando=(fabricacao + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"))
            restante = exp
            for i, pid in enumerate(pontos):
                q = restante if i == len(pontos) - 1 else exp // len(pontos)
                s._expedir(con, lote_id, pid, q, fabricacao + timedelta(days=4))
                restante -= q
            for row in con.execute("SELECT serial, ponto_id FROM caixa WHERE lote_id=? AND status='Expedido'", (lote_id,)):
                estoque_ponto.append((row[0], row[1], mid))

        r.shuffle(estoque_ponto)
        por_med = {}
        for serial, pid, mid in estoque_ponto:
            por_med.setdefault(mid, []).append((serial, pid))

        registro = {m[0]: m for m in con.execute("SELECT id, registro_anvisa FROM medicamento")}
        info_lote = {}
        for row in con.execute("SELECT c.serial, l.numero, l.validade FROM caixa c JOIN lote l ON l.id=c.lote_id"):
            info_lote[row[0]] = (row[1], row[2])

        ultimo = None
        for dia in range(DIAS):
            d = inicio + timedelta(days=dia)
            for mid, prod, exp, demanda in meds:
                for _ in range(demanda(dia, r)):
                    if not por_med.get(mid):
                        break
                    serial, pid = por_med[mid].pop()
                    numero, val = info_lote[serial]
                    ium = s.montar_ium(registro[mid][1], serial, numero, val)
                    quando = datetime.combine(d, datetime.min.time()) + timedelta(minutes=r.randint(8 * 60, 20 * 60))
                    s._validar(con, ium, pid, True, quando)
                    ultimo = (ium, pid)

        # Tentativa de CLONAGEM: a mesma caixa lida de novo em outro ponto
        if ultimo:
            outro = next(p for p in pontos if p != ultimo[1])
            s._validar(con, ultimo[0], outro, True, datetime.now() - timedelta(hours=5))
        # Tentativa de FALSIFICAÇÃO: série inexistente
        s._validar(con, f"(714){MEDICAMENTOS[0][0]}(21)FAKE00012345(10)L20260001(17)281231",
                   pontos[3], True, datetime.now() - timedelta(hours=2))

    # Uma OP manual aberta, para mostrar a fila de produção
    s.abrir_op(meds[1][0], 200)
    return True
