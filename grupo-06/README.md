# AutoFarma

**Gestão autônoma de linha de produção farmacêutica com intervenção humana**

Projeto Extensionista da disciplina Desenvolvimento de Software, Universidade Presbiteriana Mackenzie, Faculdade de Computação e Informática, 2026/2.

## Integrantes (grupo 6)

| Nome | RA |
| --- | --- |
| Eduardo Lameu Gomes | 10439169 |
| Kawe Devechi | 10434434 |
| Miguel Augusto Cardoso da Silva | 10419668 |

## A proposta

O AutoFarma integra a **Gestão de Produção** e a **Gestão de Estoque e Logística** de uma indústria farmacêutica por meio de uma linha conduzida pelo próprio sistema. O princípio do projeto é a **autonomia assimétrica**:

> O sistema pode pausar, bloquear e alertar sozinho. Retomar a linha depois de um desvio, aprovar um lote, expedir e descartar exigem uma pessoa autorizada, com assinatura eletrônica.

Todo o trabalho usa um único cenário: a linha de sólidos orais de um laboratório fictício, fabricando Paracetamol 500 mg em cinco etapas (pesagem, mistura, granulação, compressão e embalagem).

**ODS relacionados:** 3 (Saúde e Bem-Estar), 9 (Indústria, Inovação e Infraestrutura) e 12 (Consumo e Produção Responsáveis).

## Conteúdo da pasta

```
grupo-06/
├── README.md
├── relatorio/
│   ├── AutoFarma_Relatorio_Final.pdf      relatório final (padrão ABNT)
│   └── AutoFarma_Relatorio_Final.docx     mesma versão, editável
├── uml/
│   ├── 01-casos-de-uso.png
│   ├── 02-classes.png
│   ├── 03-atividades.png
│   ├── 04a-sequencia-inicio-da-ordem.png
│   ├── 04b-sequencia-desvio.png
│   ├── 05-estado.png
│   ├── 06-arquitetura.png
│   └── fontes/                            diagramas em PlantUML (.puml)
├── apresentacao/
│   └── Roteiro_da_Apresentacao.md         fala de cada integrante e roteiro da demonstração
├── telas/                                 capturas de tela do protótipo
└── prototipo/
    ├── run.py                             inicia o sistema
    ├── requirements.txt
    ├── autofarma/                         código-fonte
    │   ├── models.py                      camada de dados (classes do diagrama de classes)
    │   ├── servicos/                      camada de negócio (regras RN01 a RN14)
    │   ├── rotas.py, api.py               camada de aplicação
    │   └── templates/, static/            camada de apresentação
    └── tests/                             22 testes automatizados
```

## Entregáveis

| Entregável do enunciado | Onde está |
| --- | --- |
| Documento de requisitos (funcionais, não funcionais, priorização e regras de negócio) | Relatório, seção 4 |
| Diagramas de casos de uso, classes, atividades, sequência e estado | Relatório, seção 5, e pasta `uml/` |
| Proposta de arquitetura | Relatório, seção 6 |
| Proposta de integração de módulos | Relatório, seção 7 |
| Relatório final | `relatorio/` |
| Protótipo (não exigido) | `prototipo/` |

Em todos os diagramas, **azul** indica o que o sistema faz sozinho e **laranja** indica o que depende de uma pessoa.

## Como executar o protótipo

Requer Python 3.10 ou superior.

```bash
cd grupo-06/prototipo
python -m venv .venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Abra <http://localhost:5000>. Na primeira execução o sistema cria o banco e carrega o cenário de demonstração. Para voltar ao estado inicial: `python run.py --zerar`.

Usuários de demonstração (senha `1234` para todos):

| Usuário | Perfil | O que pode fazer |
| --- | --- | --- |
| `planejador` | Planejador de Produção | Criar ordens de produção |
| `supervisor` | Supervisor de Produção | Decidir intervenções de desvio |
| `almoxarife` | Almoxarife | Receber insumos, expedir e descartar |
| `analista` | Analista de Controle de Qualidade | Liberar insumos e aprovar ou reprovar lotes |
| `gerente` | Gerente da Qualidade | Consultar rastreabilidade e iniciar recall |

## Roteiro rápido de demonstração

1. Entre como `planejador`, abra **Ordens** e crie uma ordem. O sistema baixa os insumos por ordem de validade e assume a linha.
2. Em **Linha**, clique em **Executar um ciclo** algumas vezes (ou ligue o **Modo automático**). Depois clique em **Injetar anomalia** e execute mais um ciclo: a linha pausa sozinha.
3. Ainda como `planejador`, não há como retomar. Entre como `supervisor`, informe a justificativa e a senha e assine a decisão.
4. Deixe a linha terminar. Entre como `almoxarife`, abra **Estoque** e tente expedir o lote: o sistema recusa, porque o lote está em quarentena.
5. Entre como `analista`, abra **Qualidade**, veja o desvio registrado e aprove o lote.
6. Como `almoxarife`, expeça para dois clientes.
7. Como `gerente`, abra **Rastreabilidade**, escolha o lote de paracetamol `LI-2026-002` e inicie um recall. O sistema lista os clientes e bloqueia o saldo.
8. Abra **Auditoria**: cada ação tem autor, e as decisões do sistema aparecem em destaque.

## Como executar os testes

```bash
cd grupo-06/prototipo
python -m pytest -v
```

Cada teste traz no nome o requisito ou a regra de negócio que verifica (por exemplo, `test_rn05_leitura_fora_de_especificacao_pausa_e_o_sistema_nao_retoma`). A matriz de rastreabilidade completa está na seção 8 do relatório.

## Limitações do protótipo

- As leituras dos sensores são simuladas.
- Os requisitos de tempo de reação, desempenho e disponibilidade não foram medidos.
- A API de leituras não exige autenticação.
- O sistema não passou por validação formal e não deve ser usado em ambiente produtivo.
