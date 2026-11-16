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

**ODS relacionados:** 3 (Saúde e Bem-Estar), 9 (Indústria, Inovação e Infraestrutura) e 12 (Consumo e Produção Responsáveis).

## Conteúdo da pasta

```
grupo-06/
├── README.md
├── relatorio/           relatório final em PDF e Word (padrão ABNT)
├── uml/                 os diagramas em PNG e, em fontes/, em PlantUML
├── telas/               capturas de tela da aplicação
└── aplicacao/           a aplicação AutoFarma
    ├── run.py               inicia o sistema
    ├── simulador.py         faz o papel dos sensores da linha, pela API
    ├── autofarma/
    │   ├── models.py            camada de dados
    │   ├── servicos/            camada de negócio (todas as regras)
    │   ├── rotas.py, rotas_cadastros.py, api.py   camada de aplicação
    │   ├── agendador.py         temporizador das rotinas automáticas
    │   └── templates/, static/  camada de apresentação
    ├── tests/               38 testes automatizados
    └── Dockerfile, docker-compose.yml, .env.exemplo
```

| Entregável do enunciado | Onde está |
| --- | --- |
| Documento de requisitos | Relatório, seção 4 |
| Diagramas de casos de uso, classes, atividades, sequência e estado | Relatório, seção 5, e pasta `uml/` |
| Proposta de arquitetura | Relatório, seção 6 |
| Proposta de integração de módulos | Relatório, seção 7 |
| Relatório final | `relatorio/` |
| Aplicação (não exigida pelo enunciado) | `aplicacao/` |

Em todos os diagramas, **azul** indica o que o sistema faz sozinho e **laranja** indica o que depende de uma pessoa.

## Como executar a aplicação

Requer Python 3.10 ou superior.

```bash
cd grupo-06/aplicacao
python -m venv .venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Abra <http://localhost:5000>. Por padrão a aplicação sobe em **modo demonstração**: cria o banco, carrega o cenário de estudo (Paracetamol 500 mg) e mostra um simulador no painel. Para voltar ao estado inicial: `python run.py --zerar`.

Usuários de demonstração (senha `farma1234` para todos):

| Usuário | Perfil | O que pode fazer |
| --- | --- | --- |
| `planejador` | Planejador de Produção | Criar ordens de produção |
| `supervisor` | Supervisor de Produção | Decidir intervenções de desvio |
| `almoxarife` | Almoxarife | Receber insumos, expedir, descartar; cadastrar insumos e clientes |
| `analista` | Analista de Controle de Qualidade | Liberar insumos e aprovar ou reprovar lotes |
| `gerente` | Gerente da Qualidade | Rastreabilidade, recall, produtos, fórmulas e limites de processo |
| `admin` | Administrador do Sistema | Criar usuários, mudar perfis, desativar e redefinir senhas |

## Roteiro rápido de demonstração

1. Como `planejador`, abra **Ordens** e crie uma ordem. O sistema baixa os insumos por ordem de validade e assume a linha.
2. Em **Linha**, clique em **Executar um ciclo** algumas vezes (ou ligue o **Modo automático**). Clique em **Injetar anomalia** e execute mais um ciclo: a linha pausa sozinha.
3. O `planejador` não consegue retomar. Entre como `supervisor`, informe a justificativa e a senha e assine a decisão.
4. Deixe a linha terminar. Como `almoxarife`, tente expedir o lote em **Estoque**: o sistema recusa, porque o lote está em quarentena.
5. Como `analista`, abra **Qualidade**, veja o desvio registrado e aprove o lote.
6. Como `almoxarife`, expeça para dois clientes.
7. Como `gerente`, abra **Rastreabilidade**, escolha o lote de paracetamol `LI-2026-002` e inicie um recall. O sistema lista os clientes e bloqueia o saldo.
8. Veja **Indicadores**, o **relatório do lote** (link na Rastreabilidade) e a **Auditoria**, em que as decisões do sistema aparecem em destaque.

### Leituras por um processo externo

Em vez dos botões do painel, as leituras podem vir de fora, pela API, como viriam de um sistema supervisório. Com a aplicação rodando e uma ordem criada, em outro terminal:

```bash
python simulador.py                 # leituras normais a cada 2 segundos
python simulador.py --anomalia 5    # a quinta leitura sai fora de especificação
```

## O que a aplicação tem além do relatório

O relatório, os diagramas e os slides descrevem o fluxo central, com 25 requisitos funcionais e 14 regras de negócio. Depois de fechada a documentação, a aplicação foi ampliada. O que segue está no código e nos testes, mas **não** aparece no relatório nem nos diagramas:

| Acréscimo | Descrição |
| --- | --- |
| Cadastros pela tela | Insumos e clientes (Almoxarife); produtos, fórmulas, roteiro e limites de processo (Gerente da Qualidade, com assinatura; cada alteração gera nova versão da fórmula). |
| Perfil Administrador | Cria usuários, muda perfis, desativa e redefine senhas. Usuário nunca é excluído, só desativado. |
| Indicadores | Lotes por situação, taxa de aprovação, desvios por etapa, tempo até a decisão humana, estoque abaixo do mínimo e lotes a vencer. |
| Relatório do lote | Registro completo do lote (insumos, leituras, intervenções, liberação e expedições) pronto para imprimir. |
| Segurança | API de leituras com chave, proteção de formulários, senha mínima de 8 caracteres, troca de senha, bloqueio da conta por 5 minutos após 5 senhas erradas e validação de todos os dados de entrada. |
| Fila da linha | A linha fabrica um lote por vez. Uma segunda ordem fica na fila e o sistema a inicia sozinho quando a linha fica livre. |
| Temporizador | As rotinas de prazo e de validade rodam sozinhas em segundo plano. |
| Regras novas | A faixa de alerta deve ficar dentro da especificação; fórmula não muda com lote na linha; não se recebe insumo vencido. |

## Como executar os testes

```bash
cd grupo-06/aplicacao
python -m pytest -v
```

São 38 testes. Cada um traz no nome o requisito ou a regra que verifica (por exemplo, `test_rn05_leitura_fora_de_especificacao_pausa_e_o_sistema_nao_retoma`).

## Implantação fora do modo demonstração

Com `AUTOFARMA_DEMO=0` a aplicação sobe vazia, apenas com o usuário `admin`, e os cadastros são feitos pelas telas. Variáveis de ambiente:

| Variável | Para que serve |
| --- | --- |
| `AUTOFARMA_DEMO` | `1` (padrão) carrega o cenário e liga o simulador; `0` é o uso real |
| `AUTOFARMA_SECRET` | Chave da sessão |
| `AUTOFARMA_API_CHAVE` | Chave exigida no cabeçalho `X-API-Key` da API de leituras |
| `AUTOFARMA_ADMIN_SENHA` | Senha do primeiro administrador |
| `AUTOFARMA_BANCO` | URL do banco; sem ela, usa SQLite local |
| `AUTOFARMA_HTTPS` | `1` quando servido por HTTPS: o cookie de sessão só trafega cifrado |

Há um `Dockerfile` e um `docker-compose.yml` com PostgreSQL: copie `.env.exemplo` para `.env`, troque os valores e rode `docker compose up --build`. **A execução com `AUTOFARMA_DEMO=0` e SQLite foi testada; a implantação com Docker e PostgreSQL foi preparada, mas não foi testada.**

## Limitações

- A aplicação deve rodar em um único processo (com várias threads), como já faz o `run.py` e o `Dockerfile`: a proteção contra gravações simultâneas depende disso.
- Se existir um banco criado por uma versão anterior, rode `python run.py --zerar` uma vez.
- Não há comunicação com equipamentos reais: as leituras vêm do simulador.
- Os requisitos de tempo de reação, desempenho e disponibilidade não foram medidos.
- O sistema não passou por validação formal e não deve ser usado em uma fábrica sem ela.
