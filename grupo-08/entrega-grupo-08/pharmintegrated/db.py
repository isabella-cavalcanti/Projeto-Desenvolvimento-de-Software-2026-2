"""Camada de dados (persistência) do PharmIntegrated ERP.

Usa SQLite (já vem com o Python), então não é preciso instalar banco de dados.
Cada operação abre uma conexão própria, o que permite que a interface gráfica
e a API REST (em outra thread) usem o banco ao mesmo tempo.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

PASTA_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_caminho_banco = os.path.join(PASTA_PROJETO, "pharmintegrated.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS medicamento (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    registro_anvisa  TEXT UNIQUE NOT NULL,
    nome             TEXT NOT NULL,
    apresentacao     TEXT NOT NULL DEFAULT '',
    validade_meses   INTEGER NOT NULL DEFAULT 24
);

CREATE TABLE IF NOT EXISTS insumo (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nome     TEXT UNIQUE NOT NULL,
    unidade  TEXT NOT NULL DEFAULT 'g'
);

-- Cada recebimento de insumo é um lote do fornecedor e entra EM QUARENTENA
CREATE TABLE IF NOT EXISTS insumo_lote (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    insumo_id         INTEGER NOT NULL REFERENCES insumo(id),
    lote_fornecedor   TEXT NOT NULL,
    quantidade        REAL NOT NULL,
    saldo             REAL NOT NULL,
    validade          TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'Em Quarentena',
    data_recebimento  TEXT NOT NULL
);

-- Fórmula: quanto de cada insumo vai em UMA caixa do medicamento
CREATE TABLE IF NOT EXISTS formula (
    medicamento_id        INTEGER NOT NULL REFERENCES medicamento(id),
    insumo_id             INTEGER NOT NULL REFERENCES insumo(id),
    quantidade_por_caixa  REAL NOT NULL,
    PRIMARY KEY (medicamento_id, insumo_id)
);

CREATE TABLE IF NOT EXISTS ordem_producao (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    medicamento_id  INTEGER NOT NULL REFERENCES medicamento(id),
    quantidade      INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Aberta',
    prioridade      INTEGER NOT NULL DEFAULT 5,
    origem          TEXT NOT NULL DEFAULT 'Manual',
    data_abertura   TEXT NOT NULL,
    data_conclusao  TEXT
);

CREATE TABLE IF NOT EXISTS lote (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    numero           TEXT UNIQUE NOT NULL,
    medicamento_id   INTEGER NOT NULL REFERENCES medicamento(id),
    op_id            INTEGER REFERENCES ordem_producao(id),
    data_fabricacao  TEXT NOT NULL,
    validade         TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'Em Quarentena',
    motivo           TEXT
);

-- Vinculação biunívoca: quais lotes de insumo foram usados em cada lote final
CREATE TABLE IF NOT EXISTS consumo_insumo (
    lote_id         INTEGER NOT NULL REFERENCES lote(id),
    insumo_lote_id  INTEGER NOT NULL REFERENCES insumo_lote(id),
    quantidade      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ponto_dispensacao (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nome    TEXT UNIQUE NOT NULL,
    tipo    TEXT NOT NULL,
    cidade  TEXT NOT NULL DEFAULT ''
);

-- Cada caixa física possui um número de série único (parte do IUM)
CREATE TABLE IF NOT EXISTS caixa (
    serial            TEXT PRIMARY KEY,
    lote_id           INTEGER NOT NULL REFERENCES lote(id),
    status            TEXT NOT NULL,
    ponto_id          INTEGER REFERENCES ponto_dispensacao(id),
    data_dispensacao  TEXT
);

CREATE TABLE IF NOT EXISTS expedicao (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_id     INTEGER NOT NULL REFERENCES lote(id),
    ponto_id    INTEGER NOT NULL REFERENCES ponto_dispensacao(id),
    quantidade  INTEGER NOT NULL,
    data        TEXT NOT NULL
);

-- Registro de TODAS as tentativas de dispensação (autênticas ou não)
CREATE TABLE IF NOT EXISTS dispensacao (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ium             TEXT NOT NULL,
    serial          TEXT,
    ponto_id        INTEGER,
    medicamento_id  INTEGER,
    data            TEXT NOT NULL,
    resultado       TEXT NOT NULL,
    mensagem        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerta (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    data      TEXT NOT NULL,
    nivel     TEXT NOT NULL,
    tipo      TEXT NOT NULL,
    mensagem  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auditoria (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    data     TEXT NOT NULL,
    acao     TEXT NOT NULL,
    detalhe  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_caixa_lote ON caixa(lote_id);
CREATE INDEX IF NOT EXISTS idx_disp_data ON dispensacao(data);
"""

TABELAS = ["auditoria", "alerta", "dispensacao", "expedicao", "caixa",
           "consumo_insumo", "lote", "ordem_producao", "formula",
           "insumo_lote", "ponto_dispensacao", "insumo", "medicamento"]


def definir_caminho(caminho):
    """Permite usar outro arquivo de banco (usado nos testes)."""
    global _caminho_banco
    _caminho_banco = caminho


def caminho_banco():
    return _caminho_banco


@contextmanager
def conectar():
    con = sqlite3.connect(_caminho_banco, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def inicializar():
    with conectar() as con:
        con.executescript(SCHEMA)


def limpar_tudo():
    """Apaga todos os dados (usado ao carregar a demonstração)."""
    with conectar() as con:
        for t in TABELAS:
            con.execute(f"DROP TABLE IF EXISTS {t}")
        con.executescript(SCHEMA)


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
