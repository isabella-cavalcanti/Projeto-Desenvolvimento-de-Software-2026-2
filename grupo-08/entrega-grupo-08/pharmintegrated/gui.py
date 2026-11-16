"""Interface gráfica (camada de apresentação) do PharmIntegrated ERP — Tkinter."""
import math
import tkinter as tk
import webbrowser
from tkinter import messagebox, simpledialog, ttk

from . import api, db, demo, preditivo, servicos as s

AZUL = "#0b5d8c"
AZUL_ESCURO = "#0b3d5c"
FUNDO = "#f4f7fb"
CORES_RESULTADO = {
    s.AUTENTICO: ("#1e7d3a", "#e3f6e8"),
    s.CLONAGEM: ("#b3261e", "#fde2e2"),
    s.FALSIFICADO: ("#b3261e", "#fde2e2"),
    s.BLOQUEADO: ("#a15c00", "#fff1d6"),
    s.VENCIDO: ("#a15c00", "#fff1d6"),
    s.INVALIDO: ("#555555", "#eeeeee"),
}


# --------------------------------------------------------------------------- #
# Componentes reutilizáveis
# --------------------------------------------------------------------------- #
def tabela(pai, colunas, altura=10):
    """colunas = [(título, largura), ...]. Devolve (frame, treeview)."""
    frame = ttk.Frame(pai)
    tv = ttk.Treeview(frame, columns=[c for c, _ in colunas], show="headings", height=altura, selectmode="browse")
    for c, w in colunas:
        tv.heading(c, text=c)
        tv.column(c, width=w, minwidth=40, anchor="w")
    sb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    tv.tag_configure("vermelho", background="#fde2e2")
    tv.tag_configure("amarelo", background="#fff4d6")
    tv.tag_configure("verde", background="#e3f6e8")
    tv.tag_configure("cinza", foreground="#888888")
    return frame, tv


def preencher(tv, linhas):
    """linhas = [(id, (valores...), tag_ou_None), ...]"""
    tv.delete(*tv.get_children())
    for iid, valores, tag in linhas:
        tv.insert("", "end", iid=str(iid), values=valores, tags=(tag,) if tag else ())


def selecionado(tv, aviso="Selecione uma linha da tabela primeiro."):
    sel = tv.selection()
    if not sel:
        raise s.ErroNegocio(aviso)
    return sel[0]


def id_do_combo(combo, campo):
    valor = combo.get()
    if not valor:
        raise s.ErroNegocio(f"Escolha um item em '{campo}'.")
    return int(valor.split(" - ")[0])


def br(data_iso):
    """2026-01-31 -> 31/01/2026"""
    if not data_iso:
        return ""
    d = str(data_iso)[:10].split("-")
    return f"{d[2]}/{d[1]}/{d[0]}" + str(data_iso)[10:16] if len(d) == 3 else str(data_iso)


def ajuda(pai, texto):
    lbl = tk.Label(pai, text=texto, bg="#e4eff8", fg="#1d3b55", justify="left", anchor="w",
                   font=("Segoe UI", 10), padx=12, pady=8, wraplength=1100)
    lbl.pack(fill="x", pady=(0, 10))
    return lbl


class Formulario(ttk.LabelFrame):
    def __init__(self, pai, titulo):
        super().__init__(pai, text=titulo, padding=10)
        self.linha, self.campos = 0, {}
        self.columnconfigure(1, weight=1)

    def campo(self, nome, rotulo, combo=False, padrao=""):
        ttk.Label(self, text=rotulo).grid(row=self.linha, column=0, sticky="w", pady=3)
        w = ttk.Combobox(self, state="readonly", width=34) if combo else ttk.Entry(self, width=36)
        if padrao and not combo:
            w.insert(0, padrao)
        w.grid(row=self.linha, column=1, sticky="ew", pady=3, padx=(8, 0))
        self.campos[nome] = w
        self.linha += 1
        return w

    def botao(self, texto, comando, estilo="Acento.TButton"):
        ttk.Button(self, text=texto, command=comando, style=estilo).grid(
            row=self.linha, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.linha += 1

    def v(self, nome):
        return self.campos[nome].get().strip()

    def limpar(self, *nomes):
        for n in nomes:
            w = self.campos[n]
            w.set("") if isinstance(w, ttk.Combobox) else w.delete(0, "end")


class Aba(ttk.Frame):
    titulo = ""

    def __init__(self, app):
        super().__init__(app.abas, padding=14)
        self.app = app

    def atualizar(self):
        pass

    def acao(self, funcao):
        """Executa uma ação mostrando mensagens amigáveis em caso de erro."""
        def executar():
            try:
                funcao()
            except s.ErroNegocio as e:
                messagebox.showwarning("Atenção", str(e), parent=self)
            except Exception as e:  # erro inesperado
                messagebox.showerror("Erro", f"Ocorreu um erro inesperado:\n{e}", parent=self)
        return executar


def opcoes_medicamentos():
    return [f"{m['id']} - {m['nome']}" for m in s.listar_medicamentos()]


def opcoes_pontos():
    return [f"{p['id']} - {p['nome']} ({p['tipo']})" for p in s.listar_pontos()]


# --------------------------------------------------------------------------- #
# Aba: Painel
# --------------------------------------------------------------------------- #
class AbaPainel(Aba):
    titulo = "  Início  "

    def __init__(self, app):
        super().__init__(app)
        ajuda(self, "Bem-vindo! Este painel mostra a situação geral da fábrica. Para conhecer o sistema rapidamente, "
                    "clique em 'Carregar dados de demonstração' e depois percorra as abas da esquerda para a direita.")
        cards = ttk.Frame(self)
        cards.pack(fill="x")
        self.valores = {}
        itens = [("medicamentos", "Medicamentos cadastrados"), ("ops_abertas", "Ordens de produção abertas"),
                 ("lotes_quarentena", "Lotes aguardando o CQ"), ("caixas_disponiveis", "Caixas disponíveis"),
                 ("dispensacoes_hoje", "Dispensações hoje"), ("alertas_criticos", "Alertas críticos")]
        for i, (chave, rotulo) in enumerate(itens):
            card = tk.Frame(cards, bg="white", highlightbackground="#d6e2ee", highlightthickness=1, padx=14, pady=10)
            card.grid(row=0, column=i, sticky="nsew", padx=4)
            cards.columnconfigure(i, weight=1)
            v = tk.Label(card, text="0", bg="white", fg=AZUL, font=("Segoe UI", 22, "bold"))
            v.pack(anchor="w")
            tk.Label(card, text=rotulo, bg="white", fg="#555", font=("Segoe UI", 9)).pack(anchor="w")
            self.valores[chave] = v

        botoes = ttk.Frame(self)
        botoes.pack(fill="x", pady=12)
        ttk.Button(botoes, text="Carregar dados de demonstração", style="Acento.TButton",
                   command=self.acao(self.carregar_demo)).pack(side="left", padx=(0, 8))
        self.btn_api = ttk.Button(botoes, text="Ligar API para farmácias", command=self.acao(self.alternar_api))
        self.btn_api.pack(side="left", padx=(0, 8))
        ttk.Button(botoes, text="Abrir terminal web da farmácia",
                   command=self.acao(self.abrir_terminal)).pack(side="left")

        corpo = ttk.Frame(self)
        corpo.pack(fill="both", expand=True)
        guia = ttk.LabelFrame(corpo, text="Como usar (passo a passo)", padding=10)
        guia.pack(side="left", fill="y", padx=(0, 10))
        passos = ("1. Cadastros: medicamentos, insumos, fórmulas e pontos.\n\n"
                  "2. Qualidade: aprove os insumos recebidos\n    (eles chegam em quarentena).\n\n"
                  "3. Produção: abra uma OP e clique em\n    'Executar OP' — gera o lote e as caixas.\n\n"
                  "4. Qualidade: aprove o lote produzido.\n\n"
                  "5. Estoque: expeça caixas para um\n    hospital ou farmácia.\n\n"
                  "6. Dispensação: leia o IUM da caixa.\n    Tente ler a mesma caixa 2 vezes!\n\n"
                  "7. Planejamento: veja a previsão de\n    demanda e gere OPs automáticas.\n\n"
                  "8. Rastreabilidade: histórico completo\n    de qualquer caixa ou lote.")
        tk.Label(guia, text=passos, justify="left", bg=FUNDO, font=("Segoe UI", 10)).pack(anchor="w")

        alertas = ttk.LabelFrame(corpo, text="Últimos alertas de segurança", padding=8)
        alertas.pack(side="left", fill="both", expand=True)
        f, self.tv_alertas = tabela(alertas, [("Data", 130), ("Nível", 70), ("Tipo", 110), ("Mensagem", 640)], 14)
        f.pack(fill="both", expand=True)

    def atualizar(self):
        for chave, valor in s.resumo_painel().items():
            self.valores[chave].config(text=str(valor))
        tag = {"Crítico": "vermelho", "Alto": "amarelo", "Médio": "amarelo"}
        preencher(self.tv_alertas, [(a["id"], (br(a["data"]), a["nivel"], a["tipo"], a["mensagem"]),
                                     tag.get(a["nivel"])) for a in s.listar_alertas(100)])

    def carregar_demo(self):
        if s.listar_medicamentos() and not messagebox.askyesno(
                "Dados de demonstração", "Isso APAGA todos os dados atuais e carrega a demonstração. Continuar?",
                parent=self):
            return
        self.app.config(cursor="watch")
        self.update()
        try:
            demo.carregar()
        finally:
            self.app.config(cursor="")
        self.atualizar()
        messagebox.showinfo("Pronto", "Dados de demonstração carregados: 5 medicamentos, 4 pontos de dispensação "
                                      "e 45 dias de vendas simuladas.", parent=self)

    def alternar_api(self):
        if self.app.servidor_api:
            self.app.servidor_api.shutdown()
            self.app.servidor_api.server_close()
            self.app.servidor_api = None
            self.btn_api.config(text="Ligar API para farmácias")
        else:
            try:
                self.app.servidor_api = api.iniciar(8000)
            except OSError:
                raise s.ErroNegocio("A porta 8000 já está em uso. Feche o outro programa e tente de novo.")
            self.btn_api.config(text="Desligar API (porta 8000)")
        self.app.atualizar_status()

    def abrir_terminal(self):
        if not self.app.servidor_api:
            self.alternar_api()
        webbrowser.open("http://127.0.0.1:8000/")


# --------------------------------------------------------------------------- #
# Aba: Cadastros
# --------------------------------------------------------------------------- #
class AbaCadastros(Aba):
    titulo = "  Cadastros  "

    def __init__(self, app):
        super().__init__(app)
        ajuda(self, "Aqui ficam os dados básicos: medicamentos (com o Registro ANVISA de 13 dígitos), "
                    "insumos (matérias-primas), a fórmula de cada medicamento e os pontos de dispensação "
                    "(hospitais e farmácias). Insumos recebidos entram em QUARENTENA até o CQ aprovar.")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        # --- Medicamentos
        aba = ttk.Frame(nb, padding=10)
        nb.add(aba, text="Medicamentos")
        self.f_med = Formulario(aba, "Novo medicamento")
        self.f_med.pack(side="left", fill="y", padx=(0, 10))
        self.f_med.campo("registro", "Registro ANVISA (13 dígitos)")
        self.f_med.campo("nome", "Nome")
        self.f_med.campo("apresentacao", "Apresentação")
        self.f_med.campo("validade", "Validade (meses)", padrao="24")
        self.f_med.botao("Cadastrar medicamento", self.acao(self.cad_med))
        f, self.tv_med = tabela(aba, [("ID", 40), ("Registro ANVISA", 130), ("Nome", 230),
                                      ("Apresentação", 200), ("Validade (meses)", 110)])
        f.pack(side="left", fill="both", expand=True)

        # --- Insumos
        aba = ttk.Frame(nb, padding=10)
        nb.add(aba, text="Insumos")
        esq = ttk.Frame(aba)
        esq.pack(side="left", fill="y", padx=(0, 10))
        self.f_ins = Formulario(esq, "Novo insumo")
        self.f_ins.pack(fill="x")
        self.f_ins.campo("nome", "Nome")
        self.f_ins.campo("unidade", "Unidade (g, mL, un)", padrao="g")
        self.f_ins.botao("Cadastrar insumo", self.acao(self.cad_ins))
        self.f_rec = Formulario(esq, "Receber insumo no almoxarifado")
        self.f_rec.pack(fill="x", pady=(10, 0))
        self.f_rec.campo("insumo", "Insumo", combo=True)
        self.f_rec.campo("lote", "Lote do fornecedor")
        self.f_rec.campo("qtd", "Quantidade")
        self.f_rec.campo("validade", "Validade (DD/MM/AAAA)")
        self.f_rec.botao("Registrar recebimento", self.acao(self.receber))
        f, self.tv_ins = tabela(aba, [("ID", 40), ("Insumo", 260), ("Unidade", 70),
                                      ("Disponível (aprovado)", 150), ("Em quarentena", 120)])
        f.pack(side="left", fill="both", expand=True)

        # --- Fórmulas
        aba = ttk.Frame(nb, padding=10)
        nb.add(aba, text="Fórmulas")
        self.f_for = Formulario(aba, "Fórmula do medicamento (por caixa)")
        self.f_for.pack(side="left", fill="y", padx=(0, 10))
        self.f_for.campo("med", "Medicamento", combo=True).bind("<<ComboboxSelected>>", lambda e: self.carregar_formula())
        self.f_for.campo("insumo", "Insumo", combo=True)
        self.f_for.campo("qtd", "Quantidade por caixa")
        self.f_for.botao("Adicionar / alterar insumo", self.acao(self.add_formula))
        self.f_for.botao("Remover insumo selecionado", self.acao(self.rem_formula), "TButton")
        f, self.tv_for = tabela(aba, [("Insumo", 280), ("Quantidade por caixa", 160), ("Unidade", 80)])
        f.pack(side="left", fill="both", expand=True)

        # --- Pontos
        aba = ttk.Frame(nb, padding=10)
        nb.add(aba, text="Pontos de dispensação")
        self.f_pto = Formulario(aba, "Novo hospital / farmácia")
        self.f_pto.pack(side="left", fill="y", padx=(0, 10))
        self.f_pto.campo("nome", "Nome")
        self.f_pto.campo("tipo", "Tipo", combo=True)["values"] = ["Hospital", "Drogaria", "Distribuidora", "Clínica"]
        self.f_pto.campo("cidade", "Cidade")
        self.f_pto.botao("Cadastrar ponto", self.acao(self.cad_pto))
        f, self.tv_pto = tabela(aba, [("ID", 40), ("Nome", 280), ("Tipo", 120), ("Cidade", 180)])
        f.pack(side="left", fill="both", expand=True)

    def atualizar(self):
        meds = s.listar_medicamentos()
        preencher(self.tv_med, [(m["id"], (m["id"], m["registro_anvisa"], m["nome"], m["apresentacao"],
                                           m["validade_meses"]), None) for m in meds])
        ins = s.listar_insumos()
        preencher(self.tv_ins, [(i["id"], (i["id"], i["nome"], i["unidade"], f"{i['disponivel']:g}",
                                           f"{i['quarentena']:g}"), "amarelo" if i["quarentena"] else None)
                                for i in ins])
        opc_ins = [f"{i['id']} - {i['nome']}" for i in ins]
        self.f_rec.campos["insumo"]["values"] = opc_ins
        self.f_for.campos["insumo"]["values"] = opc_ins
        self.f_for.campos["med"]["values"] = [f"{m['id']} - {m['nome']}" for m in meds]
        preencher(self.tv_pto, [(p["id"], (p["id"], p["nome"], p["tipo"], p["cidade"]), None) for p in s.listar_pontos()])
        self.carregar_formula()

    def carregar_formula(self):
        if not self.f_for.v("med"):
            preencher(self.tv_for, [])
            return
        mid = id_do_combo(self.f_for.campos["med"], "Medicamento")
        preencher(self.tv_for, [(f["insumo_id"], (f["nome"], f"{f['quantidade_por_caixa']:g}", f["unidade"]), None)
                                for f in s.listar_formula(mid)])

    def cad_med(self):
        s.cadastrar_medicamento(self.f_med.v("registro"), self.f_med.v("nome"), self.f_med.v("apresentacao"),
                                self.f_med.v("validade"))
        self.f_med.limpar("registro", "nome", "apresentacao")
        self.atualizar()

    def cad_ins(self):
        s.cadastrar_insumo(self.f_ins.v("nome"), self.f_ins.v("unidade"))
        self.f_ins.limpar("nome")
        self.atualizar()

    def receber(self):
        s.receber_insumo(id_do_combo(self.f_rec.campos["insumo"], "Insumo"), self.f_rec.v("lote"),
                         self.f_rec.v("qtd"), self.f_rec.v("validade"))
        self.f_rec.limpar("lote", "qtd", "validade")
        self.atualizar()
        messagebox.showinfo("Recebido", "Insumo recebido e colocado EM QUARENTENA.\n"
                                        "Ele só poderá ser usado na produção depois que o CQ aprovar "
                                        "(aba Qualidade).", parent=self)

    def add_formula(self):
        s.definir_formula(id_do_combo(self.f_for.campos["med"], "Medicamento"),
                          id_do_combo(self.f_for.campos["insumo"], "Insumo"), self.f_for.v("qtd"))
        self.f_for.limpar("qtd")
        self.carregar_formula()

    def rem_formula(self):
        s.remover_da_formula(id_do_combo(self.f_for.campos["med"], "Medicamento"), int(selecionado(self.tv_for)))
        self.carregar_formula()

    def cad_pto(self):
        s.cadastrar_ponto(self.f_pto.v("nome"), self.f_pto.v("tipo"), self.f_pto.v("cidade"))
        self.f_pto.limpar("nome", "cidade")
        self.atualizar()


# --------------------------------------------------------------------------- #
# Aba: Produção
# --------------------------------------------------------------------------- #
class AbaProducao(Aba):
    titulo = "  Produção  "

    def __init__(self, app):
        super().__init__(app)
        ajuda(self, "Abra uma Ordem de Produção (OP) e clique em 'Executar OP'. O sistema confere a fórmula, "
                    "usa somente insumos APROVADOS pelo CQ, registra quais lotes de insumo foram usados, gera o "
                    "lote final e cria uma caixa com número de série único para cada unidade. "
                    "A fila é ordenada por prioridade (1 = mais urgente), que o Planejamento Preditivo ajusta.")
        corpo = ttk.Frame(self)
        corpo.pack(fill="both", expand=True)
        esq = ttk.Frame(corpo)
        esq.pack(side="left", fill="y", padx=(0, 10))
        self.f = Formulario(esq, "Nova Ordem de Produção")
        self.f.pack(fill="x")
        self.f.campo("med", "Medicamento", combo=True)
        self.f.campo("qtd", "Quantidade de caixas")
        self.f.botao("Abrir OP", self.acao(self.abrir))
        acoes = ttk.LabelFrame(esq, text="OP selecionada na tabela", padding=10)
        acoes.pack(fill="x", pady=(10, 0))
        ttk.Button(acoes, text="Executar OP (produzir lote)", style="Acento.TButton",
                   command=self.acao(self.executar)).pack(fill="x")
        ttk.Button(acoes, text="Cancelar OP", command=self.acao(self.cancelar)).pack(fill="x", pady=(6, 0))
        f, self.tv = tabela(corpo, [("OP", 50), ("Medicamento", 220), ("Caixas", 70), ("Prioridade", 80),
                                    ("Origem", 90), ("Status", 90), ("Abertura", 130), ("Lote gerado", 100)], 20)
        f.pack(side="left", fill="both", expand=True)

    def atualizar(self):
        self.f.campos["med"]["values"] = opcoes_medicamentos()
        linhas = []
        for op in s.listar_ops():
            tag = None
            if op["status"] == "Aberta":
                tag = "vermelho" if op["prioridade"] == 1 else "amarelo" if op["prioridade"] <= 3 else None
            elif op["status"] == "Cancelada":
                tag = "cinza"
            linhas.append((op["id"], (op["id"], op["medicamento"], op["quantidade"], op["prioridade"], op["origem"],
                                      op["status"], br(op["data_abertura"]), op["lote"] or ""), tag))
        preencher(self.tv, linhas)

    def abrir(self):
        s.abrir_op(id_do_combo(self.f.campos["med"], "Medicamento"), self.f.v("qtd"))
        self.f.limpar("qtd")
        self.atualizar()

    def executar(self):
        numero = s.executar_op(int(selecionado(self.tv, "Selecione uma OP na tabela.")))
        self.atualizar()
        messagebox.showinfo("Lote produzido", f"Lote {numero} gerado e colocado EM QUARENTENA.\n"
                                              "Vá até a aba Qualidade para aprová-lo.", parent=self)

    def cancelar(self):
        op = int(selecionado(self.tv, "Selecione uma OP na tabela."))
        if messagebox.askyesno("Cancelar OP", f"Cancelar a OP {op}?", parent=self):
            s.cancelar_op(op)
            self.atualizar()


# --------------------------------------------------------------------------- #
# Aba: Qualidade
# --------------------------------------------------------------------------- #
class AbaQualidade(Aba):
    titulo = "  Qualidade (CQ)  "

    def __init__(self, app):
        super().__init__(app)
        ajuda(self, "Controle de Qualidade: todo lote produzido e todo insumo recebido nasce EM QUARENTENA "
                    "(amarelo). Enquanto não for aprovado, o sistema TRAVA a produção, a expedição e a venda. "
                    "'Suspender (recall)' bloqueia um lote já aprovado e mostra na hora onde estão as caixas.")
        pl = ttk.LabelFrame(self, text="Lotes de medicamento (produto acabado)", padding=8)
        pl.pack(fill="both", expand=True)
        botoes = ttk.Frame(pl)
        botoes.pack(fill="x", pady=(0, 6))
        ttk.Button(botoes, text="Aprovar lote", style="Acento.TButton",
                   command=self.acao(self.aprovar)).pack(side="left", padx=(0, 6))
        ttk.Button(botoes, text="Reprovar lote", command=self.acao(self.reprovar)).pack(side="left", padx=(0, 6))
        ttk.Button(botoes, text="Suspender lote (recall)", command=self.acao(self.suspender)).pack(side="left", padx=(0, 6))
        ttk.Button(botoes, text="Onde estão as caixas?", command=self.acao(self.onde)).pack(side="left")
        f, self.tv_lotes = tabela(pl, [("Lote", 100), ("Medicamento", 220), ("Caixas", 70), ("Dispensadas", 90),
                                       ("Fabricação", 100), ("Validade", 100), ("Status", 110), ("Motivo", 250)], 9)
        f.pack(fill="both", expand=True)

        pi = ttk.LabelFrame(self, text="Lotes de insumo recebidos", padding=8)
        pi.pack(fill="both", expand=True, pady=(10, 0))
        botoes = ttk.Frame(pi)
        botoes.pack(fill="x", pady=(0, 6))
        ttk.Button(botoes, text="Aprovar insumo", style="Acento.TButton",
                   command=self.acao(self.aprovar_ins)).pack(side="left", padx=(0, 6))
        ttk.Button(botoes, text="Reprovar insumo", command=self.acao(self.reprovar_ins)).pack(side="left")
        f, self.tv_ins = tabela(pi, [("Insumo", 260), ("Lote fornecedor", 130), ("Recebido", 100), ("Saldo", 100),
                                     ("Unidade", 70), ("Validade", 100), ("Status", 110)], 6)
        f.pack(fill="both", expand=True)

    def atualizar(self):
        cor = {s.QUARENTENA: "amarelo", s.APROVADO: "verde", s.REPROVADO: "vermelho", s.SUSPENSO: "vermelho"}
        preencher(self.tv_lotes, [(l["id"], (l["numero"], l["medicamento"], l["caixas"], l["dispensadas"] or 0,
                                             br(l["data_fabricacao"]), br(l["validade"]), l["status"],
                                             l["motivo"] or ""), cor.get(l["status"])) for l in s.listar_lotes()])
        preencher(self.tv_ins, [(i["id"], (i["nome"], i["lote_fornecedor"], f"{i['quantidade']:g}", f"{i['saldo']:g}",
                                           i["unidade"], br(i["validade"]), i["status"]), cor.get(i["status"]))
                                for i in s.listar_insumo_lotes()])

    def _lote(self):
        return int(selecionado(self.tv_lotes, "Selecione um lote na tabela de cima."))

    def aprovar(self):
        n = s.aprovar_lote(self._lote())
        self.atualizar()
        messagebox.showinfo("Lote aprovado", f"Lote {n} liberado. As caixas agora podem ser expedidas.", parent=self)

    def reprovar(self):
        lote = self._lote()
        motivo = simpledialog.askstring("Reprovar lote", "Motivo da reprovação:", parent=self)
        if motivo:
            s.reprovar_lote(lote, motivo)
            self.atualizar()

    def suspender(self):
        lote = self._lote()
        motivo = simpledialog.askstring("Recall", "Motivo da suspensão (ex.: determinação ANVISA, desvio de qualidade):",
                                        parent=self)
        if motivo:
            rel = s.suspender_lote(lote, motivo)
            self.atualizar()
            self._mostrar_relatorio("RECALL ATIVADO — todas as caixas não dispensadas foram BLOQUEADAS.\n"
                                    "Qualquer tentativa de venda será recusada.\n\nRecolher em:", rel)

    def onde(self):
        self._mostrar_relatorio("Distribuição das caixas do lote:", s.relatorio_recall(self._lote()))

    def _mostrar_relatorio(self, titulo, rel):
        linhas = [f"• {r['local']}: {r['a_recolher']} em estoque / {r['ja_dispensadas']} já dispensadas" for r in rel]
        messagebox.showinfo("Rastreabilidade do lote", titulo + "\n\n" + "\n".join(linhas), parent=self)

    def aprovar_ins(self):
        s.aprovar_insumo_lote(int(selecionado(self.tv_ins, "Selecione um insumo na tabela de baixo.")))
        self.atualizar()

    def reprovar_ins(self):
        s.reprovar_insumo_lote(int(selecionado(self.tv_ins, "Selecione um insumo na tabela de baixo.")))
        self.atualizar()


# --------------------------------------------------------------------------- #
# Aba: Estoque e Logística
# --------------------------------------------------------------------------- #
class AbaEstoque(Aba):
    titulo = "  Estoque e Expedição  "

    def __init__(self, app):
        super().__init__(app)
        ajuda(self, "Mostra quantas caixas de cada lote estão na fábrica, expedidas, dispensadas ou bloqueadas. "
                    "Para enviar caixas a um hospital/farmácia, escolha o lote e o destino. "
                    "TRAVA DE SEGURANÇA: lotes em quarentena, reprovados, suspensos ou vencidos não podem ser expedidos.")
        corpo = ttk.Frame(self)
        corpo.pack(fill="both", expand=True)
        self.f = Formulario(corpo, "Expedir caixas")
        self.f.pack(side="left", fill="y", padx=(0, 10))
        self.f.campo("lote", "Lote", combo=True)
        self.f.campo("ponto", "Destino", combo=True)
        self.f.campo("qtd", "Quantidade de caixas")
        self.f.botao("Expedir", self.acao(self.expedir))
        f, self.tv = tabela(corpo, [("Medicamento", 180), ("Lote", 85), ("Status do lote", 100), ("Validade", 85),
                                    ("Quarentena", 75), ("Na fábrica", 70), ("Expedidas", 70),
                                    ("Dispensadas", 80), ("Bloqueadas", 75)], 20)
        f.pack(side="left", fill="both", expand=True)
        self.tv.bind("<<TreeviewSelect>>", self._ao_selecionar)
        self._mapa = {}

    def atualizar(self):
        cor = {s.QUARENTENA: "amarelo", s.REPROVADO: "vermelho", s.SUSPENSO: "vermelho"}
        dados = s.estoque_por_lote()
        preencher(self.tv, [(d["id"], (d["medicamento"], d["numero"], d["status"], br(d["validade"]), d["quarentena"],
                                       d["na_fabrica"], d["expedidas"], d["dispensadas"], d["bloqueadas"]),
                             cor.get(d["status"])) for d in dados])
        self._mapa = {d["id"]: f"{d['id']} - {d['numero']} | {d['medicamento']} | {d['status']} | "
                               f"{d['na_fabrica']} na fábrica" for d in dados}
        self.f.campos["lote"]["values"] = list(self._mapa.values())
        self.f.campos["ponto"]["values"] = opcoes_pontos()

    def _ao_selecionar(self, _):
        sel = self.tv.selection()
        if sel:
            self.f.campos["lote"].set(self._mapa[int(sel[0])])

    def expedir(self):
        s.expedir(id_do_combo(self.f.campos["lote"], "Lote"), id_do_combo(self.f.campos["ponto"], "Destino"),
                  self.f.v("qtd"))
        self.f.limpar("qtd")
        self.atualizar()
        messagebox.showinfo("Expedido", "Caixas expedidas com sucesso.", parent=self)


# --------------------------------------------------------------------------- #
# Aba: Dispensação (validação IUM)
# --------------------------------------------------------------------------- #
class AbaDispensacao(Aba):
    titulo = "  Dispensação (IUM)  "

    def __init__(self, app):
        super().__init__(app)
        ajuda(self, "Simula o leitor de DataMatrix do hospital/farmácia. O IUM tem 4 partes: Registro ANVISA (714), "
                    "Série (21), Lote (10) e Validade (17). Dê dois cliques numa caixa de exemplo à direita para "
                    "preencher o código e clique em 'Validar e dispensar'. Depois tente dispensar a MESMA caixa de "
                    "novo: o sistema detecta a clonagem (trava de segunda dispensação).")
        corpo = ttk.Frame(self)
        corpo.pack(fill="both", expand=True)
        esq = ttk.Frame(corpo)
        esq.pack(side="left", fill="both", expand=True, padx=(0, 10))

        leitor = ttk.LabelFrame(esq, text="Leitor DataMatrix", padding=10)
        leitor.pack(fill="x")
        ttk.Label(leitor, text="Ponto de dispensação").pack(anchor="w")
        self.cb_ponto = ttk.Combobox(leitor, state="readonly")
        self.cb_ponto.pack(fill="x", pady=(0, 8))
        ttk.Label(leitor, text="Código IUM").pack(anchor="w")
        self.ent_ium = ttk.Entry(leitor, font=("Consolas", 13))
        self.ent_ium.pack(fill="x", ipady=4)
        self.ent_ium.bind("<Return>", lambda e: self.acao(lambda: self.validar(True))())
        b = ttk.Frame(leitor)
        b.pack(fill="x", pady=(8, 0))
        ttk.Button(b, text="Validar e dispensar", style="Acento.TButton",
                   command=self.acao(lambda: self.validar(True))).pack(side="left", padx=(0, 6))
        ttk.Button(b, text="Só consultar (sem dar baixa)",
                   command=self.acao(lambda: self.validar(False))).pack(side="left", padx=(0, 6))
        ttk.Button(b, text="Limpar", command=lambda: self.ent_ium.delete(0, "end")).pack(side="left")

        self.resultado = tk.Label(esq, text="Aguardando leitura…", font=("Segoe UI", 16, "bold"),
                                  bg="#eeeeee", fg="#555", pady=14)
        self.resultado.pack(fill="x", pady=(10, 0))
        self.detalhe = tk.Label(esq, text="", font=("Segoe UI", 10), bg="#eeeeee", fg="#333", justify="left",
                                wraplength=620, pady=8, padx=10, anchor="w")
        self.detalhe.pack(fill="x")

        hist = ttk.LabelFrame(esq, text="Histórico de leituras", padding=6)
        hist.pack(fill="both", expand=True, pady=(10, 0))
        f, self.tv_hist = tabela(hist, [("Data", 120), ("Ponto", 170), ("Medicamento", 160),
                                        ("Resultado", 95), ("Mensagem", 400)], 8)
        f.pack(fill="both", expand=True)

        dir_ = ttk.LabelFrame(corpo, text="Caixas de exemplo (duplo clique para usar)", padding=6)
        dir_.pack(side="right", fill="both", before=esq)
        f, self.tv_ex = tabela(dir_, [("Medicamento", 170), ("Status", 100), ("Local", 175)], 24)
        f.pack(fill="both", expand=True)
        self.tv_ex.bind("<Double-1>", self._usar_exemplo)
        ttk.Button(dir_, text="Sortear outras caixas", command=self.acao(self.carregar_exemplos)).pack(fill="x", pady=(6, 0))
        self._exemplos = {}

    def atualizar(self):
        self.cb_ponto["values"] = opcoes_pontos()
        if not self.cb_ponto.get() and self.cb_ponto["values"]:
            self.cb_ponto.current(0)
        self.carregar_exemplos()
        self.carregar_historico()

    def carregar_exemplos(self):
        ex = s.iums_exemplo(40)
        self._exemplos = {e["serial"]: e for e in ex}
        cor = {s.CX_DISPENSADO: "cinza", s.CX_BLOQUEADO: "vermelho", s.CX_QUARENTENA: "amarelo"}
        preencher(self.tv_ex, [(e["serial"], (e["nome"], e["status"], e["local"]), cor.get(e["status"])) for e in ex])

    def carregar_historico(self):
        cor = {s.AUTENTICO: "verde", s.CLONAGEM: "vermelho", s.FALSIFICADO: "vermelho",
               s.BLOQUEADO: "amarelo", s.VENCIDO: "amarelo"}
        preencher(self.tv_hist, [(d["id"], (br(d["data"]), d["ponto"], d["medicamento"], d["resultado"],
                                            d["mensagem"]), cor.get(d["resultado"]))
                                 for d in s.listar_dispensacoes(150)])

    def _usar_exemplo(self, _):
        sel = self.tv_ex.selection()
        if sel:
            ex = self._exemplos[sel[0]]
            self.ent_ium.delete(0, "end")
            self.ent_ium.insert(0, ex["ium"])
            # seleciona o ponto para onde a caixa foi expedida, se houver
            for v in self.cb_ponto["values"]:
                if ex["local"] in v:
                    self.cb_ponto.set(v)

    def validar(self, dispensar):
        ponto = id_do_combo(self.cb_ponto, "Ponto de dispensação") if dispensar else None
        r = s.validar_ium(self.ent_ium.get(), ponto, dispensar)
        fg, bg = CORES_RESULTADO.get(r["resultado"], ("#333", "#eee"))
        icone = "✔" if r["ok"] else "✖"
        self.resultado.config(text=f"{icone}  {r['resultado']}", fg=fg, bg=bg)
        extra = ""
        if r["medicamento"]:
            extra = f"\nMedicamento: {r['medicamento']}   Lote: {r['lote']}   Validade: {br(r['validade'])}"
        self.detalhe.config(text=r["mensagem"] + extra, bg=bg)
        if dispensar:
            self.carregar_historico()
            self.carregar_exemplos()


# --------------------------------------------------------------------------- #
# Aba: Planejamento Preditivo
# --------------------------------------------------------------------------- #
class AbaPreditivo(Aba):
    titulo = "  Planejamento Preditivo  "

    def __init__(self, app):
        super().__init__(app)
        ajuda(self, "As vendas reais dos hospitais/farmácias alimentam a previsão de demanda (suavização exponencial "
                    "dos últimos 30 dias). O sistema calcula estoque de segurança, ponto de reposição e cobertura em "
                    "dias, e sugere quanto produzir. 'Gerar OPs sugeridas' abre as OPs e reordena a fila de produção: "
                    "evita falta de remédio (ODS 3) e superprodução que vence e vira lixo (ODS 12).")
        b = ttk.Frame(self)
        b.pack(fill="x", pady=(0, 8))
        ttk.Button(b, text="Recalcular", command=self.acao(self.atualizar)).pack(side="left", padx=(0, 6))
        ttk.Button(b, text="Gerar OPs sugeridas", style="Acento.TButton",
                   command=self.acao(self.gerar)).pack(side="left")
        ttk.Label(b, text="   Lead time: 7 dias  •  Horizonte: 30 dias  •  Nível de serviço: 95%",
                  foreground="#555").pack(side="left")
        f, self.tv = tabela(self, [("Medicamento", 200), ("Previsão/dia", 85), ("Tendência", 75), ("Estoque", 70),
                                   ("Quarentena", 80), ("Em produção", 85), ("Est. segurança", 95),
                                   ("Ponto reposição", 105), ("Cobertura (dias)", 105), ("Produzir", 70),
                                   ("Situação", 190)], 7)
        f.pack(fill="x")
        self.tv.bind("<<TreeviewSelect>>", lambda e: self.desenhar())
        quadro = ttk.LabelFrame(self, text="Demanda diária dos últimos 30 dias (selecione um medicamento acima)",
                                padding=6)
        quadro.pack(fill="both", expand=True, pady=(10, 0))
        self.canvas = tk.Canvas(quadro, bg="white", highlightthickness=0, height=220)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.desenhar())
        self._dados = {}

    def atualizar(self):
        cor = {1: "vermelho", 2: "amarelo", 3: "amarelo"}
        analise = preditivo.calcular()
        self._dados = {str(r["medicamento_id"]): r for r in analise}
        linhas = []
        for r in analise:
            cob = "∞" if math.isinf(r["cobertura"]) else f"{r['cobertura']:.1f}"
            tag = cor.get(r["prioridade"]) or ("cinza" if r["situacao"].startswith("Excesso") else None)
            linhas.append((r["medicamento_id"], (r["medicamento"], f"{r['previsao']:.1f}", r["tendencia"], r["estoque"],
                                                 r["quarentena"], r["em_producao"], r["estoque_seguranca"],
                                                 r["ponto_reposicao"], cob, r["sugestao"], r["situacao"]), tag))
        sel = self.tv.selection()
        preencher(self.tv, linhas)
        if sel and self.tv.exists(sel[0]):
            self.tv.selection_set(sel[0])
        elif linhas:
            self.tv.selection_set(str(linhas[0][0]))
        self.desenhar()

    def desenhar(self):
        c = self.canvas
        c.delete("all")
        sel = self.tv.selection()
        if not sel or sel[0] not in self._dados:
            return
        r = self._dados[sel[0]]
        serie = r["serie"]
        w, h = max(c.winfo_width(), 300), max(c.winfo_height(), 150)
        m_esq, m_inf, m_sup = 40, 25, 25
        maximo = max(max(serie, default=0), r["previsao"], 1)
        larg = (w - m_esq - 10) / max(len(serie), 1)
        escala = (h - m_inf - m_sup) / maximo
        for i in range(0, int(maximo) + 1, max(1, int(maximo // 4))):
            y = h - m_inf - i * escala
            c.create_line(m_esq, y, w - 10, y, fill="#eeeeee")
            c.create_text(m_esq - 6, y, text=str(i), anchor="e", fill="#777", font=("Segoe UI", 8))
        for i, v in enumerate(serie):
            x0 = m_esq + i * larg + 2
            c.create_rectangle(x0, h - m_inf - v * escala, x0 + larg - 4, h - m_inf, fill=AZUL, outline="")
        yp = h - m_inf - r["previsao"] * escala
        c.create_line(m_esq, yp, w - 10, yp, fill="#d9822b", width=2, dash=(6, 3))
        c.create_text(w - 12, yp - 8, text=f"previsão: {r['previsao']:.1f}/dia", anchor="e", fill="#d9822b",
                      font=("Segoe UI", 9, "bold"))
        c.create_text(m_esq, 10, text=f"{r['medicamento']} — caixas dispensadas por dia", anchor="w",
                      fill="#333", font=("Segoe UI", 9, "bold"))
        c.create_text(m_esq, h - 8, text="30 dias atrás", anchor="w", fill="#777", font=("Segoe UI", 8))
        c.create_text(w - 10, h - 8, text="ontem", anchor="e", fill="#777", font=("Segoe UI", 8))

    def gerar(self):
        criadas = preditivo.gerar_ops_sugeridas()
        self.atualizar()
        if criadas:
            txt = "\n".join(f"• OP {op}: {qtd} caixas de {med} ({sit})" for op, med, qtd, sit in criadas)
            messagebox.showinfo("OPs geradas", f"Ordens de produção abertas pela demanda real:\n\n{txt}\n\n"
                                               "A fila de produção foi reordenada por prioridade.", parent=self)
        else:
            messagebox.showinfo("OPs geradas", "Nenhuma OP nova é necessária agora. A fila foi reordenada.", parent=self)


# --------------------------------------------------------------------------- #
# Aba: Rastreabilidade e Auditoria
# --------------------------------------------------------------------------- #
class AbaRastreio(Aba):
    titulo = "  Rastreabilidade  "

    def __init__(self, app):
        super().__init__(app)
        ajuda(self, "Digite (ou cole) um IUM, um número de série ou um número de lote (ex.: L20260001) para ver "
                    "o histórico completo: insumos usados, expedições, leituras nos pontos de venda e onde estão "
                    "as caixas. Abaixo ficam todos os alertas e a trilha de auditoria (exigência das Boas Práticas).")
        linha = ttk.Frame(self)
        linha.pack(fill="x")
        self.ent = ttk.Entry(linha, font=("Consolas", 12))
        self.ent.pack(side="left", fill="x", expand=True, ipady=3)
        self.ent.bind("<Return>", lambda e: self.acao(self.rastrear)())
        ttk.Button(linha, text="Rastrear", style="Acento.TButton",
                   command=self.acao(self.rastrear)).pack(side="left", padx=(6, 0))
        self.txt = tk.Text(self, height=12, font=("Consolas", 10), bg="white", relief="flat", padx=10, pady=8)
        self.txt.pack(fill="x", pady=(8, 10))
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        a = ttk.Frame(nb, padding=6)
        nb.add(a, text="Alertas")
        f, self.tv_al = tabela(a, [("Data", 130), ("Nível", 70), ("Tipo", 110), ("Mensagem", 760)], 8)
        f.pack(fill="both", expand=True)
        a = ttk.Frame(nb, padding=6)
        nb.add(a, text="Auditoria")
        f, self.tv_au = tabela(a, [("Data", 130), ("Ação", 220), ("Detalhe", 720)], 8)
        f.pack(fill="both", expand=True)

    def atualizar(self):
        tag = {"Crítico": "vermelho", "Alto": "amarelo", "Médio": "amarelo"}
        preencher(self.tv_al, [(a["id"], (br(a["data"]), a["nivel"], a["tipo"], a["mensagem"]), tag.get(a["nivel"]))
                               for a in s.listar_alertas()])
        preencher(self.tv_au, [(a["id"], (br(a["data"]), a["acao"], a["detalhe"]), None) for a in s.listar_auditoria()])

    def rastrear(self):
        linhas = s.rastrear(self.ent.get())
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "\n".join(linhas))


# --------------------------------------------------------------------------- #
# Janela principal
# --------------------------------------------------------------------------- #
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PharmIntegrated ERP — Rastreabilidade e Gestão Preditiva")
        self.geometry("1280x800")
        self.minsize(1100, 680)
        self.configure(bg=FUNDO)
        self.servidor_api = None
        self._estilo()

        topo = tk.Frame(self, bg=AZUL_ESCURO, padx=16, pady=10)
        topo.pack(fill="x")
        tk.Label(topo, text="PharmIntegrated ERP", bg=AZUL_ESCURO, fg="white",
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        tk.Label(topo, text="   Produção • Estoque • Qualidade • Validação IUM (SNCM/ANVISA) • Manufatura preditiva",
                 bg=AZUL_ESCURO, fg="#b9d4e8", font=("Segoe UI", 10)).pack(side="left", pady=(6, 0))

        self.abas = ttk.Notebook(self)
        self.abas.pack(fill="both", expand=True, padx=10, pady=10)
        self.paginas = []
        for classe in (AbaPainel, AbaCadastros, AbaProducao, AbaQualidade, AbaEstoque,
                       AbaDispensacao, AbaPreditivo, AbaRastreio):
            pagina = classe(self)
            self.abas.add(pagina, text=classe.titulo)
            self.paginas.append(pagina)
        self.abas.bind("<<NotebookTabChanged>>", lambda e: self._ao_trocar_aba())

        self.status = tk.Label(self, anchor="w", bg="#dde6ef", fg="#333", padx=10, font=("Segoe UI", 9))
        self.status.pack(fill="x", side="bottom")
        self.atualizar_status()
        self.protocol("WM_DELETE_WINDOW", self._sair)

    def _estilo(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", font=("Segoe UI", 10), background=FUNDO)
        st.configure("TFrame", background=FUNDO)
        st.configure("TLabelframe", background=FUNDO)
        st.configure("TLabelframe.Label", background=FUNDO, foreground=AZUL_ESCURO, font=("Segoe UI", 10, "bold"))
        st.configure("TLabel", background=FUNDO)
        st.configure("TNotebook", background=FUNDO)
        st.configure("TNotebook.Tab", padding=(10, 6), font=("Segoe UI", 10))
        st.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", AZUL)])
        st.configure("Treeview", rowheight=24, font=("Segoe UI", 9))
        st.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#dde6ef")
        st.map("Treeview", background=[("selected", "#2f80b7")], foreground=[("selected", "white")])
        st.configure("TButton", padding=(10, 6))
        st.map("TCombobox", fieldbackground=[("readonly", "white")], selectbackground=[("readonly", "white")],
               selectforeground=[("readonly", "black")])
        st.configure("Acento.TButton", background=AZUL, foreground="white", padding=(10, 6))
        st.map("Acento.TButton", background=[("active", AZUL_ESCURO), ("pressed", AZUL_ESCURO)])

    def _ao_trocar_aba(self):
        pagina = self.nametowidget(self.abas.select())
        try:
            pagina.atualizar()
        except s.ErroNegocio:
            pass

    def atualizar_status(self):
        api_txt = "API ligada em http://127.0.0.1:8000" if self.servidor_api else "API desligada"
        self.status.config(text=f"Banco de dados: {db.caminho_banco()}     |     {api_txt}")

    def _sair(self):
        if self.servidor_api:
            self.servidor_api.shutdown()
        self.destroy()


def executar():
    db.inicializar()
    app = App()
    if not s.listar_medicamentos():
        if messagebox.askyesno("Primeiro uso", "O banco de dados está vazio.\n\nDeseja carregar dados de "
                                               "demonstração para conhecer o sistema?"):
            demo.carregar()
    app.paginas[0].atualizar()
    app.mainloop()
