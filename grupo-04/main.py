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




class SimuladorIAImpacto:
    """Simulacao didatica de uma IA de apoio a logistica.

    Nao utiliza aprendizado de maquina, modelo treinado nem API de IA.
    Usa regras fixas e dados ficticios para ilustrar como sugestoes
    poderiam aparecer em um sistema industrial futuro.
    """

    # Apenas para a demonstracao; NAO e um fator ambiental validado.
    FATOR_EMISSAO_FICTICIO = 0.18  # kg CO2 por quilometro

    def calcular_alerta_prazo(self, quilometros, faltantes, prazo_horas):
        """Pontuacao demonstrativa por regras fixas; NAO e previsao real.

        Mais distancia, falta de itens e menos prazo elevam o alerta.
        """
        pontos = 5 + min(55, int(quilometros / 6))
        if prazo_horas <= 6:
            pontos += 45
        elif prazo_horas <= 12:
            pontos += 25
        elif prazo_horas <= 24:
            pontos += 10
        pontos += min(20, max(0, faltantes) // 2)
        return min(100, pontos)

    def recomendar(self, sistema, codigo_bloqueado, demanda, prazo_horas, locais):
        """Sugere alternativas em cenario ficticio, sem executar expedicoes."""
        from itertools import combinations

        impedido = sistema.lotes.get(codigo_bloqueado)
        if impedido is None or impedido.status not in ("REPROVADO", "PENDENTE"):
            return {"erro": "Escolha um lote reprovado ou pendente."}

        # Garante RF09/RN01 e RN05 antes de analisar qualquer alternativa.
        elegiveis = []
        bloqueados = []
        for origem in locais:
            lote = sistema.lotes.get(origem["codigo"])
            if (lote is not None and lote.produto == impedido.produto
                    and sistema.estoque.pode_expedir(lote)):
                elegiveis.append({**origem, "quantidade": min(
                    origem["quantidade"], lote.quantidade
                )})
            else:
                bloqueados.append(origem["codigo"])

        alternativas = {}
        for n in range(1, len(elegiveis) + 1):
            for grupo in combinations(elegiveis, n):
                unidades_restantes = demanda
                alocacao = []
                for origem in sorted(grupo, key=lambda o: o["distancia_km"]):
                    quantidade = min(unidades_restantes, origem["quantidade"])
                    if quantidade > 0:
                        alocacao.append((origem, quantidade))
                        unidades_restantes -= quantidade
                    if unidades_restantes <= 0:
                        break
                if unidades_restantes > 0:
                    continue  # Nao promete atender a demanda se faltar estoque.
                chave = tuple((origem["codigo"], qtd) for origem, qtd in alocacao)
                if chave in alternativas:
                    continue
                # Rota ficticia: 1 viagem de ida e volta por centro utilizado.
                quilometros = sum(2 * origem["distancia_km"]
                                  for origem, _ in alocacao)
                alternativas[chave] = {
                    "alocacao": alocacao,
                    "quilometros": quilometros,
                    "co2_kg": round(quilometros * self.FATOR_EMISSAO_FICTICIO, 2),
                    "alerta_prazo": self.calcular_alerta_prazo(
                        quilometros, 0, prazo_horas
                    ),
                }

        return {
            "lote_bloqueado": impedido.codigo,
            "descartados": bloqueados,
            "alternativas": sorted(
                alternativas.values(),
                key=lambda a: (a["co2_kg"], a["alerta_prazo"], len(a["alocacao"]))
            ),
        }


def demonstracao_simulacao_ia():
    """Simulacao por regras fixas com dados totalmente ficticios."""
    sistema = SistemaFarmaceutico()
    fontes = [
        ("CD Central", 120, 8, "R"),
        ("CD Norte", 65, 25, "A"),
        ("CD Oeste", 80, 65, "A"),
        ("CD Sul", 120, 95, "A"),
        ("CD Leste", 90, 15, "P"),
    ]
    locais = []
    for nome, qtd, distancia, decisao in fontes:
        lote = sistema.cadastrar("Medicamento A", "MP-DEMO", qtd)
        if decisao != "P":
            sistema.avaliar(lote.codigo, decisao, "Analista CQ")
        locais.append({"nome": nome, "codigo": lote.codigo,
                       "distancia_km": distancia, "quantidade": qtd})

    codigo_bloqueado = locais[0]["codigo"]
    print("\n======= IA DE IMPACTO INTEGRADO (DEMONSTRACAO) =======")
    print("CENARIO FICTICIO: farmacia precisa de 100 unidades em 12 horas.")
    print("Lote inicialmente previsto: {} - REPROVADO.".format(codigo_bloqueado))
    print("Simulacao com regras fixas, sem IA real ou aprendizado de maquina.")
    print("Lotes reprovados ou pendentes nunca sao liberados.")
    print("\n1. BLOQUEIO OBRIGATORIO:")
    print(sistema.verificar_expedicao(codigo_bloqueado))

    simulador = SimuladorIAImpacto()
    resultado = simulador.recomendar(
        sistema, codigo_bloqueado, demanda=100, prazo_horas=12, locais=locais
    )
    print("\n2. LOTES FORA DAS SUGESTOES:")
    print(", ".join(resultado["descartados"]) or "Nenhum")
    print("\n3. ALTERNATIVAS DE ABASTECIMENTO (DADOS SIMULADOS):")
    if not resultado["alternativas"]:
        print("Nenhuma alternativa segura atende a demanda. Acionar responsavel.")
        return
    for i, proposta in enumerate(resultado["alternativas"][:3], start=1):
        print("\nAlternativa {}:".format(i))
        for origem, quantidade in proposta["alocacao"]:
            print("  {} unidades de {} (lote {})".format(
                quantidade, origem["nome"], origem["codigo"]
            ))
        print("  Distancia simulada: {} km | Emissao ilustrativa: {:.2f} kg CO2".format(
            proposta["quilometros"], proposta["co2_kg"]
        ))
        print("  Alerta de prazo SIMULADO (regras fixas): {}/100".format(
            proposta["alerta_prazo"]
        ))

    melhor = resultado["alternativas"][0]
    print("\n4. EXPLICACAO DA RECOMENDACAO:")
    print("Todos os lotes sugeridos estao APROVADOS e no estoque liberado.")
    print("Entre as combinacoes viaveis, a primeira tem a menor estimativa")
    print("de emissoes segundo as distancias e premissas ficticias cadastradas.")
    print("O alerta e gerado por REGRAS FIXAS: nao e previsao de uma IA real.")
    print("Nao ha consulta a GPS, trafego, temperaturas ou dados reais.")
    print("Nenhuma expedicao e executada: a decisao depende de verificacao humana.")
    sistema.registrar_evento(
        "Simulacao de IA para lote bloqueado {}: {} alternativas avaliadas".format(
            codigo_bloqueado, len(resultado["alternativas"])
        )
    )
    print("\nAuditoria da simulacao:")
    print(sistema.auditoria[-1])


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
        print("8 - Simulacao de IA na logistica (regras fixas)")
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

        elif opcao == "8":
            demonstracao_simulacao_ia()

        elif opcao == "0":
            print("Programa encerrado.")
            break

        else:
            print("Opcao invalida.")


if __name__ == "__main__":
    menu()
