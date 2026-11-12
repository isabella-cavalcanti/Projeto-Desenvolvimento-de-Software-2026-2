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


# ==========================================
# TESTES (Simulando o uso do sistema)
# ==========================================

if __name__ == "__main__":
    # Criando dados basicos para testar
    fornecedor1 = Fornecedor(1, "BioQuimica Insumos Ltda", "12.345.678/0001-99")
    mp1 = MateriaPrima(10, "MP-001", "Paracetamol Po", "kg", 50.0)

    lote101 = LoteMaterial(101, "LM-2026-001", "FORN-889", mp1, fornecedor1, 200.0, date(2026, 11, 1), date(2028, 11, 1))
    lote102 = LoteMaterial(102, "LM-2026-002", "FORN-890", mp1, fornecedor1, 150.0, date(2026, 11, 2), date(2028, 11, 2))

    analista = Usuario(1, "Dra. Helena Costa", "helena.qualidade", "123456", "QUALIDADE")
    almoxarife = Usuario(2, "Carlos Mendes", "carlos.almox", "654321", "ALMOXARIFE")

    # Dicionario simulando o banco de dados em memoria
    banco_lotes = {
        101: lote101,
        102: lote102
    }

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
