# Sistema Integrado para a Indústria Farmacêutica

Projeto extensionista da disciplina **Desenvolvimento de Software** — Universidade Presbiteriana Mackenzie, Faculdade de Computação e Informática.

## Objetivo

Projetar uma solução de sistema integrado para a indústria farmacêutica, cobrindo levantamento de requisitos, modelagem UML, definição de arquitetura de software e proposta de integração entre módulos.

## Escopo

- **Gestão de Produção** — controle de ordens de fabricação, lotes e rastreabilidade de insumos.
- **Controle de Qualidade** — inspeção, laudo e aprovação (ou reprovação) de cada lote fabricado.
- **Gestão de Estoque e Logística** — monitoramento de matérias-primas, embalagens, produtos acabados e alertas de validade.

**Integração proposta:** nenhum lote é liberado para o estoque sem laudo de qualidade aprovado — a aprovação no módulo de Controle de Qualidade é o evento que libera a disponibilização no módulo de Estoque. Essa regra é o ponto de integração entre módulos exigido pela proposta da disciplina (justificativa completa no Relatório Final, Seção 8).

## Objetivos de Desenvolvimento Sustentável (ODS)

- **ODS 3** — Saúde e Bem-Estar
- **ODS 9** — Indústria, Inovação e Infraestrutura
- **ODS 12** — Consumo e Produção Responsáveis

## Integrantes

- [Nome completo] — [papel no grupo]
- [Nome completo] — [papel no grupo]
- [Nome completo] — [papel no grupo]
- [Nome completo] — [papel no grupo]

## Estrutura do repositório

```
├── README.md
├── Escopo_do_Sistema.docx / .pdf    (entrega intermediária — análise de mercado, ODS e escopo dos 2 módulos obrigatórios)
├── 01-requisitos/
│   └── Documento_de_Requisitos.docx
├── 02-uml/
│   ├── casos-de-uso.png
│   ├── classes.png
│   ├── atividades.png
│   ├── sequencia.png
│   └── estado.png
├── 03-arquitetura/
│   ├── Proposta_de_Arquitetura.docx
│   └── diagrama-arquitetura.png
├── 04-relatorio-final/
│   └── Relatorio_Final.docx        (capa, sumário, análise de mercado, ODS, descrição da solução, UML, implementação em Python, arquitetura, justificativa, benefícios e referências — padrão ABNT)
├── 05-implementacao/
│   └── modelo_dominio.py           (implementação de referência das classes do domínio — sem front-end; ver Relatório Final, Seção 6)
└── video/
    ├── Slides_Apresentacao.pptx
    ├── Roteiro_Apresentacao.docx
    └── link-apresentacao.md        (adicionar o link do vídeo depois de gravado e publicado)
```

## Entregáveis

- [x] Escopo do Sistema e Análise de Mercado (entrega intermediária, já revisada)
- [x] Documento de requisitos (funcionais, não funcionais, priorização e regras de negócio)
- [x] Diagramas UML: Casos de Uso, Classes, Atividades, Sequência e Estado
- [x] Implementação de referência das classes do domínio em Python (sem front-end)
- [x] Proposta de arquitetura de sistema (camadas, tecnologias, segurança/escalabilidade/conformidade)
- [x] Relatório final (padrão ABNT, com sumário e referências)
- [x] Slides e roteiro prontos para a gravação
- [ ] Vídeo gravado e link publicado

## Vídeo de apresentação

Slides em `video/Slides_Apresentacao.pptx` (12 slides) e roteiro de fala em `video/Roteiro_Apresentacao.docx` (~5-6 minutos).
Depois de gravar, colar o link em `video/link-apresentacao.md`.

## Observação sobre fontes

No texto corrido dos documentos, referências a órgãos reguladores, associações e empresas de pesquisa de mercado foram generalizadas (ex.: "órgão regulador sanitário federal") em vez de citadas pelo nome, a pedido da professora da disciplina. Os nomes completos das fontes permanecem nas seções de Referências de cada documento, para manter a rastreabilidade acadêmica das informações.
