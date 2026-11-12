package com.rastriabilidade.de.lotes.farmacia.manager;

import com.rastriabilidade.de.lotes.farmacia.repository.*;

import org.springframework.stereotype.Component;

@Component
public class RepositoryManager {

    private final AnaliseQualidadeRepository analiseQualidadeRepository;
    private final ConsumoInsumoRepository consumoInsumoRepository;
    private final DestinoRepository destinoRepository;
    private final ExpedicaoRepository expedicaoRepository;
    private final FornecedorRepository fornecedorRepository;
    private final HistoricoStatusRepository historicoStatusRepository;
    private final ItemExpedicaoRepository itemExpedicaoRepository;
    private final LoteInsumoRepository loteInsumoRepository;
    private final LoteProdutoRepository loteProdutoRepository;
    private final ProdutoRepository produtoRepository;

    public RepositoryManager(
            AnaliseQualidadeRepository analiseQualidadeRepository,
            ConsumoInsumoRepository consumoInsumoRepository,
            DestinoRepository destinoRepository,
            ExpedicaoRepository expedicaoRepository,
            FornecedorRepository fornecedorRepository,
            HistoricoStatusRepository historicoStatusRepository,
            ItemExpedicaoRepository itemExpedicaoRepository,
            LoteInsumoRepository loteInsumoRepository,
            LoteProdutoRepository loteProdutoRepository,
            ProdutoRepository produtoRepository
    ) {
        this.analiseQualidadeRepository = analiseQualidadeRepository;
        this.consumoInsumoRepository = consumoInsumoRepository;
        this.destinoRepository = destinoRepository;
        this.expedicaoRepository = expedicaoRepository;
        this.fornecedorRepository = fornecedorRepository;
        this.historicoStatusRepository = historicoStatusRepository;
        this.itemExpedicaoRepository = itemExpedicaoRepository;
        this.loteInsumoRepository = loteInsumoRepository;
        this.loteProdutoRepository = loteProdutoRepository;
        this.produtoRepository = produtoRepository;
    }

    public AnaliseQualidadeRepository getAnaliseQualidadeRepository() {
        return analiseQualidadeRepository;
    }

    public ConsumoInsumoRepository getConsumoInsumoRepository() {
        return consumoInsumoRepository;
    }

    public DestinoRepository getDestinoRepository() {
        return destinoRepository;
    }

    public ExpedicaoRepository getExpedicaoRepository() {
        return expedicaoRepository;
    }

    public FornecedorRepository getFornecedorRepository() {
        return fornecedorRepository;
    }

    public HistoricoStatusRepository getHistoricoStatusRepository() {
        return historicoStatusRepository;
    }

    public ItemExpedicaoRepository getItemExpedicaoRepository() {
        return itemExpedicaoRepository;
    }

    public LoteInsumoRepository getLoteInsumoRepository() {
        return loteInsumoRepository;
    }

    public LoteProdutoRepository getLoteProdutoRepository() {
        return loteProdutoRepository;
    }

    public ProdutoRepository getProdutoRepository() {
        return produtoRepository;
    }
}
