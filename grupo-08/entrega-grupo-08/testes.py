"""Testes automatizados das regras de negócio (execute: python -m unittest -v testes)."""
import json
import os
import tempfile
import unittest
import urllib.request
from datetime import date, timedelta

from pharmintegrated import api, db, demo, preditivo, servicos as s


class BaseTeste(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        db.definir_caminho(os.path.join(self.pasta.name, "teste.db"))
        db.inicializar()
        validade = (date.today() + timedelta(days=400)).strftime("%d/%m/%Y")
        self.med = s.cadastrar_medicamento("1234567890123", "Remédio Teste 10 mg", "Caixa c/ 10")
        self.ins = s.cadastrar_insumo("Princípio ativo X", "g")
        self.ins_lote = s.receber_insumo(self.ins, "F-1", 1000, validade)
        s.definir_formula(self.med, self.ins, 2)
        self.h = s.cadastrar_ponto("Hospital A", "Hospital")
        self.f = s.cadastrar_ponto("Farmácia B", "Drogaria")

    def tearDown(self):
        self.pasta.cleanup()

    def produzir(self, qtd=10, aprovar=True):
        s.aprovar_insumo_lote(self.ins_lote) if self._insumo_em_quarentena() else None
        op = s.abrir_op(self.med, qtd)
        numero = s.executar_op(op)
        lote = next(l for l in s.listar_lotes() if l["numero"] == numero)
        if aprovar:
            s.aprovar_lote(lote["id"])
        return lote["id"]

    def _insumo_em_quarentena(self):
        return any(i["id"] == self.ins_lote and i["status"] == s.QUARENTENA for i in s.listar_insumo_lotes())

    def um_ium(self, lote_id):
        with db.conectar() as con:
            r = con.execute("""SELECT c.serial, l.numero, l.validade, m.registro_anvisa FROM caixa c
                               JOIN lote l ON l.id=c.lote_id JOIN medicamento m ON m.id=l.medicamento_id
                               WHERE c.lote_id=? AND c.status<>'Dispensado' LIMIT 1""", (lote_id,)).fetchone()
        return s.montar_ium(r["registro_anvisa"], r["serial"], r["numero"], r["validade"])


class TestProducaoEQualidade(BaseTeste):
    def test_insumo_em_quarentena_trava_producao(self):
        op = s.abrir_op(self.med, 10)
        with self.assertRaisesRegex(s.ErroNegocio, "insuficiente"):
            s.executar_op(op)

    def test_producao_gera_lote_caixas_e_baixa_insumo(self):
        lote = self.produzir(10)
        self.assertEqual(s.listar_insumos()[0]["disponivel"], 1000 - 20)
        self.assertEqual(next(l for l in s.listar_lotes() if l["id"] == lote)["caixas"], 10)

    def test_registro_anvisa_invalido(self):
        with self.assertRaises(s.ErroNegocio):
            s.cadastrar_medicamento("123", "X")

    def test_expedicao_bloqueada_em_quarentena(self):
        lote = self.produzir(5, aprovar=False)
        with self.assertRaisesRegex(s.ErroNegocio, "BLOQUEADA"):
            s.expedir(lote, self.h, 2)


class TestDispensacao(BaseTeste):
    def test_dispensacao_autentica(self):
        lote = self.produzir()
        s.expedir(lote, self.h, 5)
        r = s.validar_ium(self.um_ium(lote), self.h)
        self.assertEqual(r["resultado"], s.AUTENTICO)

    def test_trava_segunda_dispensacao_clonagem(self):
        lote = self.produzir()
        s.expedir(lote, self.h, 5)
        ium = self.um_ium(lote)
        self.assertTrue(s.validar_ium(ium, self.h)["ok"])
        r = s.validar_ium(ium, self.f)
        self.assertEqual(r["resultado"], s.CLONAGEM)
        self.assertEqual(s.listar_alertas()[0]["tipo"], s.CLONAGEM)

    def test_serie_inexistente_falsificado(self):
        r = s.validar_ium("(714)1234567890123(21)NAOEXISTE01(10)L20260001(17)291231", self.h)
        self.assertEqual(r["resultado"], s.FALSIFICADO)

    def test_dados_adulterados(self):
        lote = self.produzir()
        ium = self.um_ium(lote).replace("(10)L", "(10)X")
        self.assertEqual(s.validar_ium(ium, self.h)["resultado"], s.FALSIFICADO)

    def test_lote_suspenso_recall(self):
        lote = self.produzir()
        s.expedir(lote, self.h, 6)
        rel = s.suspender_lote(lote, "Determinação ANVISA")
        self.assertEqual(sum(r["a_recolher"] for r in rel), 10)
        self.assertEqual(s.validar_ium(self.um_ium(lote), self.h)["resultado"], s.BLOQUEADO)

    def test_ium_ilegivel(self):
        self.assertEqual(s.validar_ium("abc", self.h)["resultado"], s.INVALIDO)

    def test_consulta_nao_da_baixa(self):
        lote = self.produzir()
        ium = self.um_ium(lote)
        s.validar_ium(ium, dispensar=False)
        self.assertEqual(s.validar_ium(ium, self.h)["resultado"], s.AUTENTICO)


class TestPreditivoEDemo(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        db.definir_caminho(os.path.join(self.pasta.name, "demo.db"))
        demo.carregar()

    def tearDown(self):
        self.pasta.cleanup()

    def test_previsao_identifica_ruptura_e_excesso(self):
        situacoes = {r["medicamento"]: r["situacao"] for r in preditivo.calcular()}
        self.assertEqual(situacoes["Dipirona Sódica 500 mg"], "RUPTURA IMINENTE")
        self.assertTrue(situacoes["Omeprazol 20 mg"].startswith("Excesso"))

    def test_gera_ops_com_prioridade(self):
        criadas = preditivo.gerar_ops_sugeridas()
        self.assertTrue(any("Dipirona" in c[1] for c in criadas))
        primeira = s.listar_ops()[0]
        self.assertEqual((primeira["status"], primeira["prioridade"]), ("Aberta", 1))
        # rodar de novo não duplica: a OP aberta já conta como "em produção"
        self.assertFalse(any("Dipirona" in c[1] for c in preditivo.gerar_ops_sugeridas()))

    def test_rastrear_lote(self):
        texto = "\n".join(s.rastrear(s.listar_lotes()[-1]["numero"]))
        self.assertIn("Insumos utilizados", texto)

    def test_api_rest(self):
        servidor = api.iniciar(8765)
        try:
            ex = next(e for e in s.iums_exemplo(50) if e["status"] == s.CX_EXPEDIDO)
            corpo = json.dumps({"ium": ex["ium"], "ponto_id": 1}).encode()
            req = urllib.request.Request("http://127.0.0.1:8765/api/dispensar", corpo,
                                         {"Content-Type": "application/json"})
            r1 = json.loads(urllib.request.urlopen(req).read())
            r2 = json.loads(urllib.request.urlopen(req).read())
            self.assertEqual((r1["resultado"], r2["resultado"]), (s.AUTENTICO, s.CLONAGEM))
            prev = json.loads(urllib.request.urlopen("http://127.0.0.1:8765/api/previsao").read())
            self.assertEqual(len(prev), 5)
        finally:
            servidor.shutdown()
            servidor.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
