from datetime import datetime
from time import perf_counter


class Lote:
    def __init__(self, codigo, produto, materia_prima, quantidade):
        self.codigo = codigo
        self.produto = produto
        self.materia_prima = materia_prima
        self.quantidade = quantidade
        self.status = "PENDENTE"
        self.localizacao = "AGUARDANDO QUALIDADE"
        self.avaliador = "-"


class Estoque:
    def __init__(self):
        self.liberados = []
        self.quarentena = []

    def liberar(self, lote):
        if lote.status != "APROVADO":
            return False

        if lote.codigo not in self.liberados:
            self.liberados.append(lote.codigo)

        lote.localizacao = "ESTOQUE LIBERADO"
        return True

    def bloquear(self, lote):
        if lote.codigo not in self.quarentena:
            self.quarentena.append(lote.codigo)

        lote.localizacao = "QUARENTENA"

    def pode_expedir(self, lote):
        return (
            lote.status == "APROVADO"
            and lote.codigo in self.liberados
        )


class SistemaFarmaceutico:
    def __init__(self):
        self.lotes = {}
        self.estoque = Estoque()
        self.auditoria = []
        self.proximo_codigo = 1

    def registrar_evento(self, mensagem):
        horario = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.auditoria.append(horario + " | " + mensagem)

    def cadastrar(self, produto, materia_prima, quantidade):
        if not produto.strip():
            raise ValueError("Informe o produto.")

        if not materia_prima.strip():
            raise ValueError("Informe a materia-prima.")

        if quantidade <= 0:
            raise ValueError("A quantidade deve ser positiva.")

        codigo = "LT-{:03d}".format(self.proximo_codigo)
        self.proximo_codigo += 1

        lote = Lote(codigo, produto, materia_prima, quantidade)
        self.lotes[codigo] = lote

        self.registrar_evento("Lote {} cadastrado".format(codigo))

        return lote

    def avaliar(self, codigo, decisao, responsavel):
        codigo = codigo.upper()
        lote = self.lotes.get(codigo)

        if lote is None:
            return "Lote nao encontrado."

        if lote.status != "PENDENTE":
            return "Este lote ja foi avaliado."

        if not responsavel.strip():
            return "Informe o responsavel pela avaliacao."

        if decisao not in ("A", "R"):
            return "Decisao invalida. Digite A ou R."

        lote.avaliador = responsavel

        if decisao == "A":
            lote.status = "APROVADO"
            self.estoque.liberar(lote)

            mensagem = (
                "APROVADO: {} entrou no estoque liberado (RN05)."
                .format(codigo)
            )

        else:
            lote.status = "REPROVADO"
            self.estoque.bloquear(lote)

            mensagem = (
                "REPROVADO: {} bloqueado e enviado "
                "para quarentena (RN01)."
                .format(codigo)
            )

        self.registrar_evento(
            "{} | Responsavel: {}".format(mensagem, responsavel)
        )

        return mensagem

    def verificar_expedicao(self, codigo):
        codigo = codigo.upper()
        lote = self.lotes.get(codigo)

        if lote is None:
            return "Lote nao encontrado."

        if self.estoque.pode_expedir(lote):
            resultado = (
                "EXPEDICAO PERMITIDA: "
                "lote aprovado e liberado."
            )
        else:
            resultado = (
                "EXPEDICAO BLOQUEADA: "
                "lote pendente ou reprovado."
            )

        self.registrar_evento(
            "Expedicao de {}: {}".format(codigo, resultado)
        )

        return resultado

    def rastrear(self, codigo):
        inicio = perf_counter()

        codigo = codigo.upper()
        lote = self.lotes.get(codigo)

        if lote is None:
            return "Lote nao encontrado."

        dados = (
            "\nCodigo: {}\n"
            "Produto: {}\n"
            "Materia-prima: {}\n"
            "Quantidade: {}\n"
            "Status: {}\n"
            "Localizacao: {}\n"
            "Avaliado por: {}\n"
        ).format(
            lote.codigo,
            lote.produto,
            lote.materia_prima,
            lote.quantidade,
            lote.status,
            lote.localizacao,
            lote.avaliador
        )

        tempo = perf_counter() - inicio

        return dados + (
            "Tempo de consulta: {:.6f} segundos"
            .format(tempo)
        )

    def listar(self):
        if not self.lotes:
            print("Nenhum lote cadastrado.")
            return

        print("\n=== LOTES CADASTRADOS ===")

        for lote in self.lotes.values():
            print(
                "{} | {} | {} | {}".format(
                    lote.codigo,
                    lote.produto,
                    lote.status,
                    lote.localizacao
                )
            )


def demonstracao_automatica():
    sistema = SistemaFarmaceutico()

    aprovado = sistema.cadastrar(
        "Medicamento A", "MP-100", 50
    )

    reprovado = sistema.cadastrar(
        "Medicamento B", "MP-200", 30
    )

    print("\n=== ANTES DA AVALIACAO ===")

    print(
        aprovado.codigo,
        sistema.verificar_expedicao(aprovado.codigo)
    )

    print(
        reprovado.codigo,
        sistema.verificar_expedicao(reprovado.codigo)
    )

    print("\n=== CONTROLE DE QUALIDADE ===")

    print(
        sistema.avaliar(
            aprovado.codigo, "A", "Analista CQ"
        )
    )

    print(
        sistema.avaliar(
            reprovado.codigo, "R", "Analista CQ"
        )
    )

    print("\n=== DEPOIS DA AVALIACAO ===")

    print(
        aprovado.codigo,
        sistema.verificar_expedicao(aprovado.codigo)
    )

    print(
        reprovado.codigo,
        sistema.verificar_expedicao(reprovado.codigo)
    )

    print("\nESTOQUE LIBERADO:")
    print(sistema.estoque.liberados)

    print("\nQUARENTENA:")
    print(sistema.estoque.quarentena)

    print("\n=== RASTREABILIDADE ===")
    print(sistema.rastrear(aprovado.codigo))

    print("\n=== AUDITORIA ===")

    for evento in sistema.auditoria:
        print(evento)


def menu():
    sistema = SistemaFarmaceutico()

    while True:
        print("\n====================================")
        print(" SISTEMA FARMACEUTICO - GRUPO 03")
        print("====================================")
        print("1 - Cadastrar lote")
        print("2 - Aprovar ou reprovar lote")
        print("3 - Verificar expedicao")
        print("4 - Consultar rastreabilidade")
        print("5 - Listar lotes")
        print("6 - Ver auditoria")
        print("7 - Demonstracao automatica")
        print("0 - Sair")

        opcao = input("\nEscolha uma opcao: ").strip()

        if opcao == "1":
            produto = input("Produto: ")
            materia = input("Lote da materia-prima: ")

            try:
                quantidade = int(input("Quantidade: "))

                lote = sistema.cadastrar(
                    produto, materia, quantidade
                )

                print(
                    "Lote criado:", lote.codigo,
                    "- aguardando qualidade."
                )

            except ValueError as erro:
                print("Erro:", erro)

        elif opcao == "2":
            codigo = input("Codigo do lote: ").strip()
            decisao = input(
                "A = Aprovar / R = Reprovar: "
            ).strip().upper()
            responsavel = input(
                "Responsavel pela avaliacao: "
            ).strip()

            print(
                sistema.avaliar(
                    codigo, decisao, responsavel
                )
            )

        elif opcao == "3":
            codigo = input("Codigo do lote: ").strip()

            print(sistema.verificar_expedicao(codigo))

        elif opcao == "4":
            codigo = input("Codigo do lote: ").strip()

            print(sistema.rastrear(codigo))

        elif opcao == "5":
            sistema.listar()

        elif opcao == "6":
            print("\n=== HISTORICO DE AUDITORIA ===")

            if sistema.auditoria:
                for evento in sistema.auditoria:
                    print(evento)
            else:
                print("Nenhum evento registrado.")

        elif opcao == "7":
            demonstracao_automatica()

        elif opcao == "0":
            print("Programa encerrado.")
            break

        else:
            print("Opcao invalida.")


if __name__ == "__main__":
    menu()
