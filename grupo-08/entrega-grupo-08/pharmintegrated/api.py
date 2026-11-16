"""API RESTful para os Pontos de Dispensação (seção 4.2 do artigo).

É o "Gateway de Comunicação Externa": hospitais e farmácias chamam esta API
no momento da venda/administração para validar o IUM em tempo real.

Endpoints:
  GET  /                      -> terminal web de farmácia (para demonstrar)
  GET  /api/status            -> verifica se a API está no ar
  GET  /api/pontos            -> lista os pontos de dispensação
  GET  /api/validar?ium=...   -> apenas consulta a autenticidade (não dá baixa)
  POST /api/dispensar         -> corpo JSON {"ium": "...", "ponto_id": 1} — valida e dá baixa
  GET  /api/previsao          -> resultado do planejamento preditivo

Observação: aqui roda em HTTP local para fins acadêmicos. Em produção ela ficaria
atrás de HTTPS/TLS (ex.: nginx ou um API Gateway) com autenticação por token.
"""
import json
import math
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import preditivo, servicos

PAGINA = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<title>Terminal de Farmácia</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:Segoe UI,Arial;max-width:720px;margin:30px auto;padding:0 16px;background:#f4f7fb;color:#1d2b3a}
h1{color:#0b5d8c}input,select,button{font-size:16px;padding:10px;width:100%;box-sizing:border-box;margin:6px 0}
button{background:#0b5d8c;color:#fff;border:0;border-radius:6px;cursor:pointer}
#r{padding:16px;border-radius:8px;margin-top:12px;font-size:17px;display:none}</style></head><body>
<h1>Terminal do Ponto de Dispensação</h1>
<p>Simula o leitor DataMatrix de uma farmácia/hospital chamando a API do PharmIntegrated ERP.</p>
<label>Ponto de dispensação</label><select id="p"></select>
<label>IUM lido do DataMatrix</label><input id="i" placeholder="(714)...(21)...(10)...(17)...">
<button onclick="enviar()">Validar e dispensar</button>
<div id="r"></div>
<script>
fetch('/api/pontos').then(r=>r.json()).then(ps=>{for(const p of ps){const o=document.createElement('option');o.value=p.id;o.textContent=p.nome;document.getElementById('p').appendChild(o)}});
function enviar(){fetch('/api/dispensar',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({ium:document.getElementById('i').value,ponto_id:+document.getElementById('p').value})})
.then(r=>r.json()).then(d=>{const r=document.getElementById('r');r.style.display='block';
r.style.background=d.ok?'#d8f5e1':'#fbdada';r.textContent=(d.resultado||'ERRO')+' — '+(d.mensagem||d.erro)})}
</script></body></html>"""


def _limpar(obj):
    if isinstance(obj, float) and math.isinf(obj):
        return None
    if isinstance(obj, dict):
        return {k: _limpar(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_limpar(v) for v in obj]
    return obj


class _Handler(BaseHTTPRequestHandler):
    def _enviar(self, codigo, dados, tipo="application/json"):
        corpo = dados.encode("utf-8") if isinstance(dados, str) else \
            json.dumps(_limpar(dados), ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *args):  # silencia o log no terminal
        pass

    def do_GET(self):
        url = urlparse(self.path)
        try:
            if url.path == "/":
                return self._enviar(200, PAGINA, "text/html")
            if url.path == "/api/status":
                return self._enviar(200, {"status": "online", "sistema": "PharmIntegrated ERP"})
            if url.path == "/api/pontos":
                return self._enviar(200, servicos.listar_pontos())
            if url.path == "/api/validar":
                ium = parse_qs(url.query).get("ium", [""])[0]
                return self._enviar(200, servicos.validar_ium(ium, dispensar=False))
            if url.path == "/api/previsao":
                return self._enviar(200, preditivo.calcular())
            self._enviar(404, {"erro": "endpoint não encontrado"})
        except servicos.ErroNegocio as e:
            self._enviar(400, {"erro": str(e)})

    def do_POST(self):
        if urlparse(self.path).path != "/api/dispensar":
            return self._enviar(404, {"erro": "endpoint não encontrado"})
        try:
            tamanho = int(self.headers.get("Content-Length", 0))
            dados = json.loads(self.rfile.read(tamanho) or b"{}")
            res = servicos.validar_ium(dados.get("ium", ""), dados.get("ponto_id"), dispensar=True)
            self._enviar(200, res)
        except (servicos.ErroNegocio, ValueError) as e:
            self._enviar(400, {"erro": str(e)})


def iniciar(porta=8000):
    """Sobe a API em segundo plano e devolve o servidor (use .shutdown() para parar)."""
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), _Handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


if __name__ == "__main__":
    from . import db
    db.inicializar()
    print("API do PharmIntegrated ERP em http://127.0.0.1:8000  (Ctrl+C para sair)")
    ThreadingHTTPServer(("127.0.0.1", 8000), _Handler).serve_forever()
