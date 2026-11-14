import json
from datetime import date, datetime

# ==========================================
# MODEL - Classes de Dominio e Regras
# ==========================================

class Fornecedor:
    def __init__(self, id, razao_social, cnpj, qualificado=True):
        self.id = id
        self.razao_social = razao_social
        self.cnpj = cnpj
        self.qualificado = qualificado


class MateriaPrima:
    def __init__(self, id, codigo, nome, unidade_medida, estoque_minimo):
        self.id = id
        self.codigo = codigo
        self.nome = nome
        self.unidade_medida = unidade_medida
        self.estoque_minimo = estoque_minimo


class Usuario:
    def __init__(self, id, nome, login, senha, perfil, ativo=True):
        self.id = id
        self.nome = nome
        self.login = login
        self.senhaHash = "hash_" + senha
        self.perfil = perfil
        self.ativo = ativo

    def autenticar(self, senha):
        return self.ativo and self.senhaHash == ("hash_" + senha)

    def temPermissao(self, acao):
        if not self.ativo:
            return False
        if acao == "AVALIAR_LOTE_MATERIAL" and self.perfil == "QUALIDADE":
            return True
        if acao == "REGISTRAR_RECEBIMENTO" and self.perfil == "ALMOXARIFE":
            return True
        return False


class DecisaoQualidade:
    def __init__(self, id, decisao, justificativa, usuario):
        self.id = id
        self.decisao = decisao
        self.justificativa = justificativa
        self.usuario = usuario
        self.dataHora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class LoteMaterial:
    def __init__(self, id, numero_lote, lote_fornecedor, materia_prima, fornecedor, qtd_recebida, data_recebimento, data_validade):
        self.id = id
        self.numeroLote = numero_lote
        self.loteFornecedor = lote_fornecedor
        self.materiaPrima = materia_prima
        self.fornecedor = fornecedor
        self.quantidadeRecebida = qtd_recebida
        self.saldoAtual = qtd_recebida
        self.dataRecebimento = data_recebimento
        self.dataValidade = data_validade
        self.status = "QUARENTENA"
        self.historicoDecisoes = []

    def estaVencido(self):
        return self.dataValidade < date.today()

    def podeSerConsumido(self, qtd):
        return self.status == "APROVADO" and not self.estaVencido() and self.saldoAtual >= qtd and qtd > 0

    def baixarSaldo(self, qtd):
        if not self.podeSerConsumido(qtd):
            raise Exception("Lote nao pode ser consumido ou saldo insuficiente.")
        self.saldoAtual -= qtd
        if self.saldoAtual == 0:
            self.status = "ESGOTADO"

    def aprovar(self, usuario, justificativa):
        if not usuario.temPermissao("AVALIAR_LOTE_MATERIAL"):
            raise Exception(f"Acesso negado: usuario '{usuario.nome}' ({usuario.perfil}) nao tem perfil QUALIDADE.")
        if self.status != "QUARENTENA":
            raise Exception(f"Bloqueado: o lote '{self.numeroLote}' esta com status '{self.status}'. So lotes em QUARENTENA podem ser avaliados.")
        if not justificativa or justificativa.strip() == "":
            raise Exception("A justificativa e obrigatoria.")
        if self.estaVencido():
            self.status = "VENCIDO"
            raise Exception("Bloqueado: o lote esta vencido.")

        self.status = "APROVADO"
        nova_decisao = DecisaoQualidade(len(self.historicoDecisoes) + 1, "APROVADO", justificativa, usuario)
        self.historicoDecisoes.append(nova_decisao)
        return nova_decisao

    def reprovar(self, usuario, justificativa):
        if not usuario.temPermissao("AVALIAR_LOTE_MATERIAL"):
            raise Exception(f"Acesso negado: usuario '{usuario.nome}' ({usuario.perfil}) nao tem perfil QUALIDADE.")
        if self.status != "QUARENTENA":
            raise Exception(f"Bloqueado: o lote '{self.numeroLote}' esta com status '{self.status}'. So lotes em QUARENTENA podem ser avaliados.")
        if not justificativa or justificativa.strip() == "":
            raise Exception("A justificativa e obrigatoria para reprovar o lote.")

        self.status = "REPROVADO"
        nova_decisao = DecisaoQualidade(len(self.historicoDecisoes) + 1, "REPROVADO", justificativa, usuario)
        self.historicoDecisoes.append(nova_decisao)
        return nova_decisao
# ==========================================
# VIEW - Exibicao dos Resultados (JSON/Texto)
# ==========================================

class AvaliacaoQualidadeView:
    def renderizarSucesso(self, lote, decisao):
        dados = {
            "status_requisicao": "SUCESSO",
            "lote": lote.numeroLote,
            "materia_prima": lote.materiaPrima.nome,
            "novo_status": lote.status,
            "decisao": {
                "id": decisao.id,
                "resultado": decisao.decisao,
                "justificativa": decisao.justificativa,
                "analista": decisao.usuario.nome,
                "data_hora": decisao.dataHora
            }
        }
        return json.dumps(dados, indent=4, ensure_ascii=False)

    def renderizarHistorico(self, lote):
        lista = []
        for d in lote.historicoDecisoes:
            lista.append({
                "id": d.id,
                "decisao": d.decisao,
                "justificativa": d.justificativa,
                "usuario": d.usuario.nome,
                "data_hora": d.dataHora
            })
        dados = {
            "lote": lote.numeroLote,
            "status_atual": lote.status,
            "historico": lista
        }
        return json.dumps(dados, indent=4, ensure_ascii=False)

    def renderizarErro(self, mensagem):
        dados = {
            "status_requisicao": "ERRO",
            "motivo": mensagem
        }
        return json.dumps(dados, indent=4, ensure_ascii=False)

    def renderizarListaLotes(self, lotes):
        lista = []
        for l in lotes:
            lista.append({
                "id": l.id,
                "lote": l.numeroLote,
                "materia_prima": l.materiaPrima.nome,
                "status": l.status,
                "saldo_atual": l.saldoAtual,
                "validade": l.dataValidade.isoformat()
            })
        return json.dumps({"lotes": lista}, indent=4, ensure_ascii=False)

    def renderizarRecebimento(self, lote):
        dados = {
            "status_requisicao": "SUCESSO",
            "mensagem": "Lote recebido e enviado para QUARENTENA.",
            "id": lote.id,
            "lote": lote.numeroLote,
            "lote_fornecedor": lote.loteFornecedor,
            "materia_prima": lote.materiaPrima.nome,
            "fornecedor": lote.fornecedor.razao_social,
            "quantidade_recebida": lote.quantidadeRecebida,
            "validade": lote.dataValidade.isoformat(),
            "status": lote.status
        }
        return json.dumps(dados, indent=4, ensure_ascii=False)


# ==========================================
# CONTROLLER - Intermediario entre View e Model
# ==========================================

class AvaliacaoQualidadeController:
    def __init__(self, banco_lotes, view):
        self.banco_lotes = banco_lotes
        self.view = view

    def avaliarLote(self, lote_id, usuario, decisao, justificativa):
        lote = self.banco_lotes.get(lote_id)
        if not lote:
            return self.view.renderizarErro("Lote nao encontrado.")

        try:
            if decisao == "APROVADO":
                reg = lote.aprovar(usuario, justificativa)
            elif decisao == "REPROVADO":
                reg = lote.reprovar(usuario, justificativa)
            else:
                return self.view.renderizarErro("Decisao invalida.")

            return self.view.renderizarSucesso(lote, reg)
        except Exception as erro:
            return self.view.renderizarErro(str(erro))

    def consultarHistoricoLote(self, lote_id):
        lote = self.banco_lotes.get(lote_id)
        if not lote:
            return self.view.renderizarErro("Lote nao encontrado.")
        return self.view.renderizarHistorico(lote)

    def listarLotes(self):
        return self.view.renderizarListaLotes(list(self.banco_lotes.values()))

    def registrarRecebimento(self, usuario, numero_lote, lote_fornecedor, materia_prima, fornecedor, quantidade, data_validade):
        if not usuario.temPermissao("REGISTRAR_RECEBIMENTO"):
            return self.view.renderizarErro(f"Acesso negado: usuario '{usuario.nome}' ({usuario.perfil}) nao tem perfil ALMOXARIFE.")
        if not numero_lote or not numero_lote.strip() or not lote_fornecedor or not lote_fornecedor.strip():
            return self.view.renderizarErro("Numero do lote e lote do fornecedor sao obrigatorios.")
        try:
            qtd = float(str(quantidade).replace(",", "."))
            validade = date.fromisoformat(str(data_validade).strip())
        except ValueError:
            return self.view.renderizarErro("Quantidade ou data de validade invalida (use o formato AAAA-MM-DD).")
        if qtd <= 0:
            return self.view.renderizarErro("A quantidade recebida deve ser maior que zero.")
        for existente in self.banco_lotes.values():
            if existente.numeroLote == numero_lote.strip():
                return self.view.renderizarErro(f"Ja existe um lote com o numero '{numero_lote.strip()}'.")

        novo_id = max(self.banco_lotes.keys(), default=100) + 1
        lote = LoteMaterial(novo_id, numero_lote.strip(), lote_fornecedor.strip(), materia_prima, fornecedor,
            qtd, date.today(), validade)
        self.banco_lotes[novo_id] = lote
        return self.view.renderizarRecebimento(lote)


# ==========================================
# DADOS INICIAIS (simulando o banco de dados)
# ==========================================

def criarDadosIniciais():
    fornecedor1 = Fornecedor(1, "BioQuimica Insumos Ltda", "12.345.678/0001-99")
    mp1 = MateriaPrima(10, "MP-001", "Paracetamol Po", "kg", 50.0)

    lote101 = LoteMaterial(101, "LM-2026-001", "FORN-889", mp1, fornecedor1, 200.0, date(2026, 11, 1), date(2028, 11, 1))
    lote102 = LoteMaterial(102, "LM-2026-002", "FORN-890", mp1, fornecedor1, 150.0, date(2026, 11, 2), date(2028, 11, 2))

    analista = Usuario(1, "Dra. Helena Costa", "helena.qualidade", "8", "QUALIDADE")
    almoxarife = Usuario(2, "Carlos Mendes", "carlos.almox", "9", "ALMOXARIFE")

    # Dicionario simulando o banco de dados em memoria
    banco_lotes = {
        101: lote101,
        102: lote102
    }
    return fornecedor1, mp1, analista, almoxarife, banco_lotes


# ==========================================
# TESTES (Simulando o uso do sistema)
# ==========================================

def executarCenariosDeTeste():
    fornecedor1, mp1, analista, almoxarife, banco_lotes = criarDadosIniciais()
    view = AvaliacaoQualidadeView()
    controller = AvaliacaoQualidadeController(banco_lotes, view)

    print("--- CENARIO 1: Aprovando lote 101 em Quarentena (UC03) ---")
    print(controller.avaliarLote(101, analista, "APROVADO", "Laudo conferido e material aprovado."))

    print("\n--- CENARIO 2: Reprovando lote 102 em Quarentena (UC03 / UC14) ---")
    print(controller.avaliarLote(102, analista, "REPROVADO", "Embalagem violada e com umidade."))

    print("\n--- CENARIO 3: Tentativa de aprovacao por Almoxarife (Bloqueio de Perfil) ---")
    print(controller.avaliarLote(101, almoxarife, "APROVADO", "Tentando aprovar pelo almoxarifado."))

    print("\n--- CENARIO 4: Tentativa de avaliar lote que nao esta mais em Quarentena ---")
    print(controller.avaliarLote(101, analista, "REPROVADO", "Tentando mudar lote ja aprovado."))

    print("\n--- CENARIO 5: Consultando historico do lote 101 ---")
    print(controller.consultarHistoricoLote(101))


# ==========================================
# MENU INTERATIVO NO TERMINAL (entrada do usuario)
# ==========================================

def lerInteiro(texto):
    valor = input(texto).strip()
    try:
        return int(valor)
    except ValueError:
        return None


def pausar():
    input("\nPressione ENTER para voltar ao menu...")


def fazerLogin(usuarios):
    while True:
        print("\n=== LOGIN ===")
        for i, u in enumerate(usuarios, start=1):
            print(f"{i} - {u.nome} ({u.perfil}) | login: {u.login}")
        opcao = lerInteiro("Escolha o usuario: ")
        if opcao is None or opcao < 1 or opcao > len(usuarios):
            print(">> Opcao invalida.")
            continue
        usuario = usuarios[opcao - 1]
        senha = input(f"Senha de {usuario.login}: ")
        if usuario.autenticar(senha):
            print(f">> Bem-vindo(a), {usuario.nome}!")
            return usuario
        print(">> Senha incorreta. Tente novamente.")


def executarMenu():
    fornecedor1, mp1, analista, almoxarife, banco_lotes = criarDadosIniciais()
    view = AvaliacaoQualidadeView()
    controller = AvaliacaoQualidadeController(banco_lotes, view)
    usuarios = [analista, almoxarife]
    usuario = fazerLogin(usuarios)

    while True:
        print("\n==================================================")
        print(" RASTROFARMA - Controle de Qualidade (MVC)")
        print(f" Usuario logado: {usuario.nome} ({usuario.perfil})")
        print("==================================================")
        print("1 - Listar lotes")
        print("2 - Registrar recebimento de lote (Almoxarife)")
        print("3 - Avaliar lote em quarentena (Qualidade)")
        print("4 - Consultar historico de um lote")
        print("5 - Trocar usuario")
        print("6 - Executar os 5 cenarios de teste automaticos")
        print("0 - Sair")
        opcao = input("Escolha uma opcao: ").strip()

        if opcao == "1":
            print(controller.listarLotes())
        elif opcao == "2":
            numero = input("Numero do lote (ex.: LM-2026-003): ")
            lote_forn = input("Lote do fornecedor (ex.: FORN-891): ")
            qtd = input("Quantidade recebida em kg: ")
            validade = input("Data de validade (AAAA-MM-DD): ")
            print(controller.registrarRecebimento(usuario, numero, lote_forn, mp1, fornecedor1, qtd, validade))
        elif opcao == "3":
            lote_id = lerInteiro("ID do lote (ex.: 101): ")
            print("Decisao: 1 - APROVAR | 2 - REPROVAR")
            escolha = input("Escolha: ").strip()
            decisao = {"1": "APROVADO", "2": "REPROVADO"}.get(escolha, escolha)
            justificativa = input("Justificativa: ")
            print(controller.avaliarLote(lote_id, usuario, decisao, justificativa))
        elif opcao == "4":
            lote_id = lerInteiro("ID do lote: ")
            print(controller.consultarHistoricoLote(lote_id))
        elif opcao == "5":
            usuario = fazerLogin(usuarios)
            continue
        elif opcao == "6":
            print()
            executarCenariosDeTeste()
        elif opcao == "0":
            print("Encerrando o sistema. Ate logo!")
            break
        else:
            print(">> Opcao invalida. Digite um numero de 0 a 6.")
            continue
        pausar()


if __name__ == "__main__":
    import sys
    try:
        if "--testes" in sys.argv:
            executarCenariosDeTeste()
        else:
            executarMenu()
    except (KeyboardInterrupt, EOFError):
        print("\nEncerrando o sistema. Ate logo!")
