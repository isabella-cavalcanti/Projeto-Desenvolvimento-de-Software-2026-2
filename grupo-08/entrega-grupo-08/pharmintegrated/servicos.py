"""Camada de regras de negócio do PharmIntegrated ERP.

Módulos (conforme o artigo, seção 4):
  * Cadastros ............ medicamentos, insumos, fórmulas e pontos de dispensação
  * Gestão de Produção ... Ordens de Produção (OP), consumo de insumos, geração de lotes
  * Controle de Qualidade  quarentena, aprovação, reprovação e suspensão (recall)
  * Estoque e Logística .. estoque por lote e expedição com trava de quarentena
  * Dispensação .......... validação do IUM em tempo real e trava de 2ª dispensação
  * Rastreabilidade ...... histórico completo de uma caixa ou lote
"""
import calendar
import re
import secrets
from datetime import date, datetime

from . import db

# Status do ciclo de vida (Diagrama de Estados do artigo)
QUARENTENA = "Em Quarentena"
APROVADO = "Aprovado"
REPROVADO = "Reprovado"
SUSPENSO = "Suspenso"

CX_QUARENTENA = "Em Quarentena"
CX_ESTOQUE = "Aprovado/Estoque"
CX_EXPEDIDO = "Expedido"
CX_DISPENSADO = "Dispensado"
CX_BLOQUEADO = "Bloqueado"

# Resultados possíveis da validação de um IUM
AUTENTICO = "AUTÊNTICO"
INVALIDO = "INVÁLIDO"
FALSIFICADO = "FALSIFICADO"
CLONAGEM = "CLONAGEM"
BLOQUEADO = "BLOQUEADO"
VENCIDO = "VENCIDO"


class ErroNegocio(Exception):
    """Erro de regra de negócio, com mensagem pronta para mostrar ao usuário."""


# --------------------------------------------------------------------------- #
# Utilitários
# --------------------------------------------------------------------------- #
def somar_meses(d, meses):
    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def _auditar(con, acao, detalhe, quando=None):
    con.execute("INSERT INTO auditoria (data, acao, detalhe) VALUES (?,?,?)",
                (quando or db.agora(), acao, detalhe))


def _alertar(con, nivel, tipo, mensagem, quando=None):
    con.execute("INSERT INTO alerta (data, nivel, tipo, mensagem) VALUES (?,?,?,?)",
                (quando or db.agora(), nivel, tipo, mensagem))


def _texto(valor, campo):
    valor = (valor or "").strip()
    if not valor:
        raise ErroNegocio(f"Preencha o campo '{campo}'.")
    return valor


def _numero(valor, campo, inteiro=False):
    try:
        n = int(valor) if inteiro else float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        raise ErroNegocio(f"O campo '{campo}' precisa ser um número.")
    if n <= 0:
        raise ErroNegocio(f"O campo '{campo}' precisa ser maior que zero.")
    return n


def _data(valor, campo):
    try:
        return datetime.strptime(str(valor).strip(), "%d/%m/%Y").date()
    except ValueError:
        raise ErroNegocio(f"O campo '{campo}' deve estar no formato DD/MM/AAAA.")


# --------------------------------------------------------------------------- #
# Cadastros
# --------------------------------------------------------------------------- #
def cadastrar_medicamento(registro, nome, apresentacao="", validade_meses=24):
    registro = _texto(registro, "Registro ANVISA").replace(".", "").replace("-", "")
    if not (registro.isdigit() and len(registro) == 13):
        raise ErroNegocio("O Registro ANVISA deve ter 13 dígitos numéricos.")
    nome = _texto(nome, "Nome")
    validade_meses = _numero(validade_meses, "Validade (meses)", inteiro=True)
    with db.conectar() as con:
        if con.execute("SELECT 1 FROM medicamento WHERE registro_anvisa=?", (registro,)).fetchone():
            raise ErroNegocio("Já existe um medicamento com esse Registro ANVISA.")
        cur = con.execute(
            "INSERT INTO medicamento (registro_anvisa, nome, apresentacao, validade_meses) VALUES (?,?,?,?)",
            (registro, nome, apresentacao.strip(), validade_meses))
        _auditar(con, "Cadastro de medicamento", f"{nome} (reg. {registro})")
        return cur.lastrowid


def listar_medicamentos():
    with db.conectar() as con:
        return [dict(r) for r in con.execute("SELECT * FROM medicamento ORDER BY nome")]


def cadastrar_insumo(nome, unidade="g"):
    nome = _texto(nome, "Nome do insumo")
    with db.conectar() as con:
        if con.execute("SELECT 1 FROM insumo WHERE nome=?", (nome,)).fetchone():
            raise ErroNegocio("Esse insumo já está cadastrado.")
        cur = con.execute("INSERT INTO insumo (nome, unidade) VALUES (?,?)", (nome, _texto(unidade, "Unidade")))
        _auditar(con, "Cadastro de insumo", nome)
        return cur.lastrowid


def listar_insumos():
    """Insumos com o saldo aprovado (disponível) e o saldo em quarentena."""
    sql = """
        SELECT i.id, i.nome, i.unidade,
               COALESCE(SUM(CASE WHEN il.status='Aprovado' THEN il.saldo END), 0) AS disponivel,
               COALESCE(SUM(CASE WHEN il.status='Em Quarentena' THEN il.saldo END), 0) AS quarentena
        FROM insumo i LEFT JOIN insumo_lote il ON il.insumo_id = i.id
        GROUP BY i.id ORDER BY i.nome"""
    with db.conectar() as con:
        return [dict(r) for r in con.execute(sql)]


def receber_insumo(insumo_id, lote_fornecedor, quantidade, validade_ddmmaaaa):
    """Recebimento no almoxarifado: o lote do insumo entra sempre EM QUARENTENA."""
    lote_fornecedor = _texto(lote_fornecedor, "Lote do fornecedor")
    quantidade = _numero(quantidade, "Quantidade")
    validade = _data(validade_ddmmaaaa, "Validade")
    if validade <= date.today():
        raise ErroNegocio("Não é permitido receber insumo já vencido.")
    with db.conectar() as con:
        cur = con.execute(
            """INSERT INTO insumo_lote (insumo_id, lote_fornecedor, quantidade, saldo, validade, status, data_recebimento)
               VALUES (?,?,?,?,?,?,?)""",
            (insumo_id, lote_fornecedor, quantidade, quantidade, validade.isoformat(), QUARENTENA, db.agora()))
        _auditar(con, "Recebimento de insumo", f"insumo {insumo_id}, lote {lote_fornecedor}, {quantidade}")
        return cur.lastrowid


def listar_insumo_lotes():
    sql = """SELECT il.*, i.nome, i.unidade FROM insumo_lote il JOIN insumo i ON i.id = il.insumo_id
             ORDER BY CASE il.status WHEN 'Em Quarentena' THEN 0 ELSE 1 END, il.id DESC"""
    with db.conectar() as con:
        return [dict(r) for r in con.execute(sql)]


def definir_formula(medicamento_id, insumo_id, quantidade_por_caixa):
    q = _numero(quantidade_por_caixa, "Quantidade por caixa")
    with db.conectar() as con:
        con.execute("""INSERT INTO formula (medicamento_id, insumo_id, quantidade_por_caixa) VALUES (?,?,?)
                       ON CONFLICT(medicamento_id, insumo_id) DO UPDATE SET quantidade_por_caixa=excluded.quantidade_por_caixa""",
                    (medicamento_id, insumo_id, q))
        _auditar(con, "Fórmula alterada", f"medicamento {medicamento_id}: insumo {insumo_id} = {q}/caixa")


def remover_da_formula(medicamento_id, insumo_id):
    with db.conectar() as con:
        con.execute("DELETE FROM formula WHERE medicamento_id=? AND insumo_id=?", (medicamento_id, insumo_id))
        _auditar(con, "Fórmula alterada", f"medicamento {medicamento_id}: insumo {insumo_id} removido")


def listar_formula(medicamento_id):
    sql = """SELECT f.insumo_id, i.nome, i.unidade, f.quantidade_por_caixa FROM formula f
             JOIN insumo i ON i.id = f.insumo_id WHERE f.medicamento_id=? ORDER BY i.nome"""
    with db.conectar() as con:
        return [dict(r) for r in con.execute(sql, (medicamento_id,))]


def cadastrar_ponto(nome, tipo, cidade=""):
    nome = _texto(nome, "Nome do ponto")
    with db.conectar() as con:
        if con.execute("SELECT 1 FROM ponto_dispensacao WHERE nome=?", (nome,)).fetchone():
            raise ErroNegocio("Já existe um ponto com esse nome.")
        cur = con.execute("INSERT INTO ponto_dispensacao (nome, tipo, cidade) VALUES (?,?,?)",
                          (nome, _texto(tipo, "Tipo"), cidade.strip()))
        _auditar(con, "Cadastro de ponto de dispensação", nome)
        return cur.lastrowid


def listar_pontos():
    with db.conectar() as con:
        return [dict(r) for r in con.execute("SELECT * FROM ponto_dispensacao ORDER BY nome")]


# --------------------------------------------------------------------------- #
# Gestão de Produção
# --------------------------------------------------------------------------- #
def _abrir_op(con, medicamento_id, quantidade, origem="Manual", prioridade=5, quando=None):
    cur = con.execute(
        "INSERT INTO ordem_producao (medicamento_id, quantidade, status, prioridade, origem, data_abertura) VALUES (?,?,?,?,?,?)",
        (medicamento_id, quantidade, "Aberta", prioridade, origem, quando or db.agora()))
    _auditar(con, "OP aberta", f"OP {cur.lastrowid}: {quantidade} caixas do medicamento {medicamento_id} ({origem})", quando)
    return cur.lastrowid


def abrir_op(medicamento_id, quantidade, origem="Manual", prioridade=5):
    quantidade = _numero(quantidade, "Quantidade de caixas", inteiro=True)
    with db.conectar() as con:
        if not con.execute("SELECT 1 FROM formula WHERE medicamento_id=?", (medicamento_id,)).fetchone():
            raise ErroNegocio("Esse medicamento ainda não tem fórmula cadastrada (aba Cadastros > Fórmulas).")
        return _abrir_op(con, medicamento_id, quantidade, origem, prioridade)


def listar_ops():
    sql = """SELECT op.*, m.nome AS medicamento, l.numero AS lote FROM ordem_producao op
             JOIN medicamento m ON m.id = op.medicamento_id
             LEFT JOIN lote l ON l.op_id = op.id
             ORDER BY CASE op.status WHEN 'Aberta' THEN 0 ELSE 1 END, op.prioridade, op.id"""
    with db.conectar() as con:
        return [dict(r) for r in con.execute(sql)]


def cancelar_op(op_id):
    with db.conectar() as con:
        op = con.execute("SELECT status FROM ordem_producao WHERE id=?", (op_id,)).fetchone()
        if not op or op["status"] != "Aberta":
            raise ErroNegocio("Só é possível cancelar uma OP com status 'Aberta'.")
        con.execute("UPDATE ordem_producao SET status='Cancelada', data_conclusao=? WHERE id=?", (db.agora(), op_id))
        _auditar(con, "OP cancelada", f"OP {op_id}")


def _executar_op(con, op_id, quando=None):
    quando = quando or datetime.now()
    op = con.execute("SELECT * FROM ordem_producao WHERE id=?", (op_id,)).fetchone()
    if not op or op["status"] != "Aberta":
        raise ErroNegocio("Só é possível executar uma OP com status 'Aberta'.")
    med = con.execute("SELECT * FROM medicamento WHERE id=?", (op["medicamento_id"],)).fetchone()
    formula = con.execute("SELECT f.*, i.nome, i.unidade FROM formula f JOIN insumo i ON i.id=f.insumo_id "
                          "WHERE medicamento_id=?", (med["id"],)).fetchall()
    if not formula:
        raise ErroNegocio("Esse medicamento não tem fórmula cadastrada.")

    # 1) Verifica se há insumo APROVADO (e não vencido) suficiente para toda a OP
    plano = []
    for item in formula:
        necessario = item["quantidade_por_caixa"] * op["quantidade"]
        lotes = con.execute(
            """SELECT * FROM insumo_lote WHERE insumo_id=? AND status='Aprovado' AND saldo>0 AND validade>=?
               ORDER BY validade, id""", (item["insumo_id"], quando.date().isoformat())).fetchall()
        disponivel = sum(l["saldo"] for l in lotes)
        if disponivel + 1e-9 < necessario:
            raise ErroNegocio(
                f"Insumo insuficiente: {item['nome']}. Necessário {necessario:g} {item['unidade']}, "
                f"disponível (aprovado pelo CQ) {disponivel:g} {item['unidade']}.")
        plano.append((necessario, lotes))

    # 2) Cria o lote do produto acabado (entra EM QUARENTENA)
    ano = quando.year
    seq = con.execute("SELECT COUNT(*) FROM lote WHERE numero LIKE ?", (f"L{ano}%",)).fetchone()[0] + 1
    numero = f"L{ano}{seq:04d}"
    validade = somar_meses(quando.date(), med["validade_meses"])
    cur = con.execute(
        "INSERT INTO lote (numero, medicamento_id, op_id, data_fabricacao, validade, status) VALUES (?,?,?,?,?,?)",
        (numero, med["id"], op_id, quando.date().isoformat(), validade.isoformat(), QUARENTENA))
    lote_id = cur.lastrowid

    # 3) Baixa os insumos (FEFO: vence primeiro, sai primeiro) e registra o vínculo insumo -> lote
    for necessario, lotes in plano:
        restante = necessario
        for il in lotes:
            if restante <= 1e-9:
                break
            usar = min(il["saldo"], restante)
            con.execute("UPDATE insumo_lote SET saldo = saldo - ? WHERE id=?", (usar, il["id"]))
            con.execute("INSERT INTO consumo_insumo (lote_id, insumo_lote_id, quantidade) VALUES (?,?,?)",
                        (lote_id, il["id"], usar))
            restante -= usar

    # 4) Gera as caixas com número de série aleatório e imprevisível (dificulta falsificação)
    seriais = set()
    while len(seriais) < op["quantidade"]:
        seriais.add(secrets.token_hex(6).upper())
    con.executemany("INSERT INTO caixa (serial, lote_id, status) VALUES (?,?,?)",
                    [(s, lote_id, CX_QUARENTENA) for s in seriais])

    con.execute("UPDATE ordem_producao SET status='Concluída', data_conclusao=? WHERE id=?",
                (quando.strftime("%Y-%m-%d %H:%M:%S"), op_id))
    _auditar(con, "OP executada", f"OP {op_id} gerou o lote {numero} com {op['quantidade']} caixas",
             quando.strftime("%Y-%m-%d %H:%M:%S"))
    return numero


def executar_op(op_id):
    with db.conectar() as con:
        return _executar_op(con, op_id)


# --------------------------------------------------------------------------- #
# Controle de Qualidade (CQ)
# --------------------------------------------------------------------------- #
def listar_lotes():
    sql = """SELECT l.*, m.nome AS medicamento, m.registro_anvisa,
                    COUNT(c.serial) AS caixas,
                    SUM(c.status='Dispensado') AS dispensadas
             FROM lote l JOIN medicamento m ON m.id = l.medicamento_id
             LEFT JOIN caixa c ON c.lote_id = l.id
             GROUP BY l.id
             ORDER BY CASE l.status WHEN 'Em Quarentena' THEN 0 ELSE 1 END, l.id DESC"""
    with db.conectar() as con:
        return [dict(r) for r in con.execute(sql)]


def _mudar_status_lote(con, lote_id, novo, motivo=None, quando=None):
    lote = con.execute("SELECT * FROM lote WHERE id=?", (lote_id,)).fetchone()
    if not lote:
        raise ErroNegocio("Lote não encontrado.")
    atual = lote["status"]
    permitidos = {
        APROVADO: [QUARENTENA],
        REPROVADO: [QUARENTENA],
        SUSPENSO: [APROVADO],
    }
    if atual not in permitidos[novo]:
        raise ErroNegocio(f"Não é possível mudar o lote {lote['numero']} de '{atual}' para '{novo}'.")
    con.execute("UPDATE lote SET status=?, motivo=? WHERE id=?", (novo, motivo, lote_id))
    if novo == APROVADO:
        con.execute("UPDATE caixa SET status=? WHERE lote_id=? AND status=?", (CX_ESTOQUE, lote_id, CX_QUARENTENA))
    else:
        con.execute("UPDATE caixa SET status=? WHERE lote_id=? AND status<>?", (CX_BLOQUEADO, lote_id, CX_DISPENSADO))
    _auditar(con, f"CQ: lote {novo.lower()}", f"{lote['numero']}" + (f" — motivo: {motivo}" if motivo else ""), quando)
    return lote["numero"]


def aprovar_lote(lote_id, quando=None):
    with db.conectar() as con:
        return _mudar_status_lote(con, lote_id, APROVADO, quando=quando)


def reprovar_lote(lote_id, motivo):
    with db.conectar() as con:
        return _mudar_status_lote(con, lote_id, REPROVADO, _texto(motivo, "Motivo"))


def suspender_lote(lote_id, motivo):
    """Recall: bloqueia todas as caixas ainda não dispensadas e devolve onde elas estão."""
    with db.conectar() as con:
        numero = _mudar_status_lote(con, lote_id, SUSPENSO, _texto(motivo, "Motivo"))
        _alertar(con, "Alto", "Recall", f"Lote {numero} SUSPENSO. Motivo: {motivo}")
    return relatorio_recall(lote_id)


def relatorio_recall(lote_id):
    """Mostra em segundos onde estão as caixas do lote (problema da 'Empresa A')."""
    sql = """SELECT COALESCE(p.nome, 'Fábrica (depósito próprio)') AS local,
                    SUM(c.status <> 'Dispensado') AS a_recolher,
                    SUM(c.status = 'Dispensado') AS ja_dispensadas
             FROM caixa c LEFT JOIN ponto_dispensacao p ON p.id = c.ponto_id
             WHERE c.lote_id=? GROUP BY local ORDER BY a_recolher DESC"""
    with db.conectar() as con:
        return [dict(r) for r in con.execute(sql, (lote_id,))]


def aprovar_insumo_lote(insumo_lote_id, quando=None):
    _status_insumo(insumo_lote_id, APROVADO, quando)


def reprovar_insumo_lote(insumo_lote_id):
    _status_insumo(insumo_lote_id, REPROVADO)


def _status_insumo(insumo_lote_id, novo, quando=None):
    with db.conectar() as con:
        il = con.execute("SELECT * FROM insumo_lote WHERE id=?", (insumo_lote_id,)).fetchone()
        if not il or il["status"] != QUARENTENA:
            raise ErroNegocio("Só é possível aprovar/reprovar insumos que estão 'Em Quarentena'.")
        con.execute("UPDATE insumo_lote SET status=? WHERE id=?", (novo, insumo_lote_id))
        _auditar(con, f"CQ: insumo {novo.lower()}", f"lote de insumo {il['lote_fornecedor']}", quando)


# --------------------------------------------------------------------------- #
# Estoque e Logística
# --------------------------------------------------------------------------- #
def estoque_por_lote():
    sql = """SELECT l.id, l.numero, l.status, l.validade, m.nome AS medicamento,
                    SUM(c.status='Em Quarentena') AS quarentena,
                    SUM(c.status='Aprovado/Estoque') AS na_fabrica,
                    SUM(c.status='Expedido') AS expedidas,
                    SUM(c.status='Dispensado') AS dispensadas,
                    SUM(c.status='Bloqueado') AS bloqueadas
             FROM lote l JOIN medicamento m ON m.id=l.medicamento_id
             JOIN caixa c ON c.lote_id=l.id
             GROUP BY l.id ORDER BY m.nome, l.validade"""
    with db.conectar() as con:
        return [dict(r) for r in con.execute(sql)]


def _expedir(con, lote_id, ponto_id, quantidade, quando=None):
    lote = con.execute("SELECT * FROM lote WHERE id=?", (lote_id,)).fetchone()
    if not lote:
        raise ErroNegocio("Lote não encontrado.")
    # TRAVA DE SEGURANÇA: lote em quarentena / reprovado / suspenso não sai da fábrica
    if lote["status"] != APROVADO:
        raise ErroNegocio(f"EXPEDIÇÃO BLOQUEADA: o lote {lote['numero']} está '{lote['status']}'. "
                          "Somente lotes aprovados pelo Controle de Qualidade podem ser expedidos.")
    data_ref = (quando or datetime.now()).date().isoformat()
    if lote["validade"] < data_ref:
        raise ErroNegocio(f"EXPEDIÇÃO BLOQUEADA: o lote {lote['numero']} está vencido.")
    caixas = con.execute("SELECT serial FROM caixa WHERE lote_id=? AND status=? LIMIT ?",
                         (lote_id, CX_ESTOQUE, quantidade)).fetchall()
    if len(caixas) < quantidade:
        raise ErroNegocio(f"Só há {len(caixas)} caixas desse lote no depósito da fábrica.")
    con.executemany("UPDATE caixa SET status=?, ponto_id=? WHERE serial=?",
                    [(CX_EXPEDIDO, ponto_id, c["serial"]) for c in caixas])
    q = quando.strftime("%Y-%m-%d %H:%M:%S") if quando else db.agora()
    con.execute("INSERT INTO expedicao (lote_id, ponto_id, quantidade, data) VALUES (?,?,?,?)",
                (lote_id, ponto_id, quantidade, q))
    _auditar(con, "Expedição", f"{quantidade} caixas do lote {lote['numero']} para o ponto {ponto_id}", q)


def expedir(lote_id, ponto_id, quantidade):
    quantidade = _numero(quantidade, "Quantidade", inteiro=True)
    if not ponto_id:
        raise ErroNegocio("Escolha o ponto de dispensação de destino.")
    with db.conectar() as con:
        _expedir(con, lote_id, ponto_id, quantidade)


# --------------------------------------------------------------------------- #
# Dispensação: IUM (Identificador Único de Medicamento)
# --------------------------------------------------------------------------- #
# Formato legível do DataMatrix no padrão GS1 usado pelo SNCM:
#   (714) Registro ANVISA  (21) Número de série  (10) Lote  (17) Validade AAMMDD
_RE_IUM = re.compile(r"\((\d{2,4})\)([^()]+)")


def montar_ium(registro, serial, lote, validade_iso):
    v = date.fromisoformat(validade_iso)
    return f"(714){registro}(21){serial}(10){lote}(17){v.strftime('%y%m%d')}"


def ler_ium(texto):
    partes = dict(_RE_IUM.findall((texto or "").strip().replace(" ", "")))
    faltando = [ai for ai in ("714", "21", "10", "17") if ai not in partes]
    if faltando:
        raise ErroNegocio("Código IUM ilegível ou incompleto. Formato esperado: "
                          "(714)REGISTRO(21)SERIE(10)LOTE(17)AAMMDD")
    try:
        validade = datetime.strptime(partes["17"], "%y%m%d").date()
    except ValueError:
        raise ErroNegocio("Data de validade do IUM inválida.")
    return {"registro": partes["714"], "serial": partes["21"].upper(),
            "lote": partes["10"], "validade": validade}


def _validar(con, ium, ponto_id=None, dispensar=True, quando=None):
    quando = quando or datetime.now()
    q = quando.strftime("%Y-%m-%d %H:%M:%S")
    if dispensar and not ponto_id:
        raise ErroNegocio("Escolha o ponto de dispensação.")
    nome_ponto = ""
    if ponto_id:
        p = con.execute("SELECT nome FROM ponto_dispensacao WHERE id=?", (ponto_id,)).fetchone()
        nome_ponto = p["nome"] if p else f"ponto {ponto_id}"

    info = {"ium": ium, "medicamento": "", "lote": "", "validade": "", "serial": ""}

    def resposta(resultado, mensagem, nivel=None, med_id=None):
        if dispensar:  # toda tentativa de dispensação fica registrada
            con.execute("""INSERT INTO dispensacao (ium, serial, ponto_id, medicamento_id, data, resultado, mensagem)
                           VALUES (?,?,?,?,?,?,?)""",
                        (ium, info["serial"] or None, ponto_id, med_id, q, resultado, mensagem))
            if nivel:
                _alertar(con, nivel, resultado, f"[{nome_ponto}] {mensagem} — IUM {ium}", q)
        return dict(info, ok=(resultado == AUTENTICO), resultado=resultado, mensagem=mensagem)

    try:
        dados = ler_ium(ium)
    except ErroNegocio as e:
        return resposta(INVALIDO, str(e))
    info["serial"] = dados["serial"]

    cx = con.execute(
        """SELECT c.*, l.numero, l.validade AS lote_validade, l.status AS lote_status, l.medicamento_id,
                  m.registro_anvisa, m.nome, p.nome AS ponto_nome
           FROM caixa c JOIN lote l ON l.id=c.lote_id JOIN medicamento m ON m.id=l.medicamento_id
           LEFT JOIN ponto_dispensacao p ON p.id=c.ponto_id
           WHERE c.serial=?""", (dados["serial"],)).fetchone()

    if not cx:
        return resposta(FALSIFICADO, "Número de série NÃO EXISTE na base da indústria. "
                                     "Possível medicamento falsificado — NÃO dispensar.", "Crítico")
    info.update(medicamento=cx["nome"], lote=cx["numero"], validade=cx["lote_validade"])
    med_id = cx["medicamento_id"]

    if (cx["registro_anvisa"] != dados["registro"] or cx["numero"] != dados["lote"]
            or cx["lote_validade"] != dados["validade"].isoformat()):
        return resposta(FALSIFICADO, "Os dados impressos (registro/lote/validade) NÃO conferem com o "
                                     "cadastro desta série. Embalagem adulterada — NÃO dispensar.", "Crítico", med_id)

    if cx["status"] == CX_DISPENSADO:
        return resposta(CLONAGEM, f"Este IUM JÁ FOI DISPENSADO em {cx['ponto_nome'] or '?'} em "
                                  f"{cx['data_dispensacao']}. Suspeita de embalagem clonada — operação bloqueada.",
                        "Crítico", med_id)

    if cx["lote_status"] in (SUSPENSO, REPROVADO) or cx["status"] == CX_BLOQUEADO:
        return resposta(BLOQUEADO, f"O lote {cx['numero']} está {cx['lote_status'].upper()} "
                                   "(recall/reprovação). NÃO dispensar e devolver à indústria.", "Alto", med_id)

    if cx["lote_status"] == QUARENTENA or cx["status"] == CX_QUARENTENA:
        return resposta(BLOQUEADO, f"O lote {cx['numero']} ainda está em quarentena e não foi liberado "
                                   "pelo Controle de Qualidade. NÃO dispensar.", "Alto", med_id)

    if dados["validade"] < quando.date():
        return resposta(VENCIDO, f"Medicamento VENCIDO em {dados['validade'].strftime('%d/%m/%Y')}. NÃO dispensar.",
                        "Médio", med_id)

    aviso = ""
    if dispensar:
        if cx["status"] == CX_ESTOQUE:
            aviso = " Atenção: a caixa não consta como expedida pela indústria."
            _alertar(con, "Médio", "Desvio", f"[{nome_ponto}] caixa {dados['serial']} dispensada sem registro "
                                             "de expedição", q)
        elif cx["ponto_id"] and cx["ponto_id"] != ponto_id:
            aviso = f" Atenção: a caixa foi expedida para '{cx['ponto_nome']}'."
            _alertar(con, "Médio", "Desvio", f"[{nome_ponto}] caixa {dados['serial']} expedida para "
                                             f"'{cx['ponto_nome']}'", q)
        con.execute("UPDATE caixa SET status=?, ponto_id=?, data_dispensacao=? WHERE serial=?",
                    (CX_DISPENSADO, ponto_id, q, dados["serial"]))
        return resposta(AUTENTICO, f"Medicamento autêntico. Dispensação registrada.{aviso}", None, med_id)
    return resposta(AUTENTICO, "Medicamento autêntico e liberado para dispensação (apenas consulta).", None, med_id)


def validar_ium(ium, ponto_id=None, dispensar=True):
    """Valida o IUM lido no ponto de venda. Se dispensar=True, registra a baixa."""
    with db.conectar() as con:
        return _validar(con, ium, ponto_id, dispensar)


def iums_exemplo(limite=30):
    """IUMs de caixas reais para facilitar testes e apresentações."""
    sql = """SELECT c.serial, c.status, l.numero, l.validade, m.registro_anvisa, m.nome,
                    COALESCE(p.nome, 'Fábrica') AS local
             FROM caixa c JOIN lote l ON l.id=c.lote_id JOIN medicamento m ON m.id=l.medicamento_id
             LEFT JOIN ponto_dispensacao p ON p.id=c.ponto_id
             ORDER BY CASE c.status WHEN 'Expedido' THEN 0 WHEN 'Aprovado/Estoque' THEN 1
                      WHEN 'Dispensado' THEN 2 ELSE 3 END, RANDOM() LIMIT ?"""
    with db.conectar() as con:
        linhas = []
        for r in con.execute(sql, (limite,)):
            d = dict(r)
            d["ium"] = montar_ium(r["registro_anvisa"], r["serial"], r["numero"], r["validade"])
            linhas.append(d)
        return linhas


def listar_dispensacoes(limite=200):
    sql = """SELECT d.*, COALESCE(p.nome,'') AS ponto, COALESCE(m.nome,'') AS medicamento
             FROM dispensacao d LEFT JOIN ponto_dispensacao p ON p.id=d.ponto_id
             LEFT JOIN medicamento m ON m.id=d.medicamento_id ORDER BY d.id DESC LIMIT ?"""
    with db.conectar() as con:
        return [dict(r) for r in con.execute(sql, (limite,))]


# --------------------------------------------------------------------------- #
# Rastreabilidade, alertas, auditoria e painel
# --------------------------------------------------------------------------- #
def rastrear(texto):
    """Recebe um IUM, um número de série ou um número de lote e devolve o histórico."""
    texto = (texto or "").strip()
    if not texto:
        raise ErroNegocio("Digite um IUM, um número de série ou um número de lote.")
    serial = None
    if "(21)" in texto:
        serial = ler_ium(texto)["serial"]
    linhas = []
    with db.conectar() as con:
        if serial is None and con.execute("SELECT 1 FROM caixa WHERE serial=?", (texto.upper(),)).fetchone():
            serial = texto.upper()
        if serial:
            cx = con.execute("""SELECT c.*, p.nome AS ponto FROM caixa c
                                LEFT JOIN ponto_dispensacao p ON p.id=c.ponto_id WHERE serial=?""",
                             (serial,)).fetchone()
            if not cx:
                raise ErroNegocio("Número de série não encontrado: possível falsificação.")
            linhas.append(f"CAIXA {serial}")
            linhas.append(f"  Status atual: {cx['status']}")
            linhas.append(f"  Local: {cx['ponto'] or 'Fábrica'}")
            if cx["data_dispensacao"]:
                linhas.append(f"  Dispensada em: {cx['data_dispensacao']}")
            tentativas = con.execute("""SELECT d.data, d.resultado, COALESCE(p.nome,'?') AS ponto FROM dispensacao d
                                        LEFT JOIN ponto_dispensacao p ON p.id=d.ponto_id
                                        WHERE d.serial=? ORDER BY d.id""", (serial,)).fetchall()
            if tentativas:
                linhas.append("  Leituras no ponto de venda:")
                for t in tentativas:
                    linhas.append(f"    {t['data']}  {t['resultado']:<12} {t['ponto']}")
            lote_id = cx["lote_id"]
            linhas.append("")
        else:
            l = con.execute("SELECT id FROM lote WHERE numero=?", (texto.upper(),)).fetchone()
            if not l:
                raise ErroNegocio("Nada encontrado. Verifique o IUM, a série ou o lote digitado.")
            lote_id = l["id"]

        lote = con.execute("""SELECT l.*, m.nome, m.registro_anvisa FROM lote l
                              JOIN medicamento m ON m.id=l.medicamento_id WHERE l.id=?""", (lote_id,)).fetchone()
        linhas.append(f"LOTE {lote['numero']} — {lote['nome']} (Reg. ANVISA {lote['registro_anvisa']})")
        linhas.append(f"  Status: {lote['status']}" + (f" — motivo: {lote['motivo']}" if lote["motivo"] else ""))
        linhas.append(f"  Fabricação: {lote['data_fabricacao']}   Validade: {lote['validade']}   OP: {lote['op_id']}")
        linhas.append("  Insumos utilizados (vínculo insumo → lote):")
        for r in con.execute("""SELECT i.nome, i.unidade, il.lote_fornecedor, ci.quantidade FROM consumo_insumo ci
                                JOIN insumo_lote il ON il.id=ci.insumo_lote_id JOIN insumo i ON i.id=il.insumo_id
                                WHERE ci.lote_id=?""", (lote_id,)):
            linhas.append(f"    - {r['nome']}: {r['quantidade']:g} {r['unidade']} (lote fornecedor {r['lote_fornecedor']})")
        linhas.append("  Expedições:")
        exps = con.execute("""SELECT e.data, e.quantidade, p.nome FROM expedicao e
                              JOIN ponto_dispensacao p ON p.id=e.ponto_id WHERE e.lote_id=? ORDER BY e.id""",
                           (lote_id,)).fetchall()
        for e in exps:
            linhas.append(f"    - {e['data']}: {e['quantidade']} caixas → {e['nome']}")
        if not exps:
            linhas.append("    (nenhuma)")
    linhas.append("  Onde estão as caixas deste lote:")
    for r in relatorio_recall(lote_id):
        linhas.append(f"    - {r['local']}: {r['a_recolher']} em estoque, {r['ja_dispensadas']} já dispensadas")
    return linhas


def listar_alertas(limite=200):
    with db.conectar() as con:
        return [dict(r) for r in con.execute("SELECT * FROM alerta ORDER BY id DESC LIMIT ?", (limite,))]


def listar_auditoria(limite=300):
    with db.conectar() as con:
        return [dict(r) for r in con.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,))]


def resumo_painel():
    hoje = date.today().isoformat()
    with db.conectar() as con:
        um = lambda sql, *a: con.execute(sql, a).fetchone()[0] or 0  # noqa: E731
        return {
            "medicamentos": um("SELECT COUNT(*) FROM medicamento"),
            "ops_abertas": um("SELECT COUNT(*) FROM ordem_producao WHERE status='Aberta'"),
            "lotes_quarentena": um("SELECT COUNT(*) FROM lote WHERE status='Em Quarentena'")
                                + um("SELECT COUNT(*) FROM insumo_lote WHERE status='Em Quarentena'"),
            "caixas_disponiveis": um("SELECT COUNT(*) FROM caixa WHERE status IN ('Aprovado/Estoque','Expedido')"),
            "dispensacoes_hoje": um("SELECT COUNT(*) FROM dispensacao WHERE resultado=? AND substr(data,1,10)=?",
                                    AUTENTICO, hoje),
            "alertas_criticos": um("SELECT COUNT(*) FROM alerta WHERE nivel='Crítico'"),
        }
