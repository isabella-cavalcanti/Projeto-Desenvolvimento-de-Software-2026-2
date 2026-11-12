package com.rastriabilidade.de.lotes.farmacia.dataInitializer;

import org.springframework.core.annotation.Order;
import java.time.LocalDate;
import java.time.LocalDateTime;

import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import com.rastriabilidade.de.lotes.farmacia.enuns.StatusLote;
import com.rastriabilidade.de.lotes.farmacia.manager.RepositoryManager;
import com.rastriabilidade.de.lotes.farmacia.model.AnaliseQualidade;
import com.rastriabilidade.de.lotes.farmacia.model.ConsumoInsumo;
import com.rastriabilidade.de.lotes.farmacia.model.Destino;
import com.rastriabilidade.de.lotes.farmacia.model.Expedicao;
import com.rastriabilidade.de.lotes.farmacia.model.Fornecedor;
import com.rastriabilidade.de.lotes.farmacia.model.HistoricoStatus;
import com.rastriabilidade.de.lotes.farmacia.model.ItemExpedicao;
import com.rastriabilidade.de.lotes.farmacia.model.LoteInsumo;
import com.rastriabilidade.de.lotes.farmacia.model.LoteProduto;
import com.rastriabilidade.de.lotes.farmacia.model.Produto;

@Component
@Order(1)
public class DataInitializer implements CommandLineRunner {

    private final RepositoryManager repositoryManager;

    public DataInitializer(
            RepositoryManager repositoryManager
    ) {
        this.repositoryManager = repositoryManager;
    }

    @Override
    @Transactional
    public void run(String... args) {
        Produto produtoA = obterOuCriarProduto(
                "Produto de demonstração A",
                "Registro fictício para testar a rastreabilidade"
        );
        Produto produtoB = obterOuCriarProduto(
                "Produto de demonstração B",
                "Registro fictício para testar a rastreabilidade"
        );

        LoteProduto lote001 = obterOuCriarLote(
                "DEMO-LOTE-001",
                produtoA,
                StatusLote.EXPEDIDO,
                LocalDate.now().minusMonths(2),
                LocalDate.now().plusMonths(10)
        );
        LoteProduto lote002 = obterOuCriarLote(
                "DEMO-LOTE-002",
                produtoA,
                StatusLote.EM_QUARENTENA,
                LocalDate.now().minusMonths(1),
                LocalDate.now().plusMonths(11)
        );
        LoteProduto lote003 = obterOuCriarLote(
                "DEMO-LOTE-003",
                produtoB,
                StatusLote.EM_PRODUCAO,
                LocalDate.now(),
                LocalDate.now().plusMonths(12)
        );

        if (repositoryManager.getFornecedorRepository().count() > 0) {
            return;
        }

        registrarDadosDeSuporte(lote001, lote002, lote003);
    }

    private void registrarDadosDeSuporte(LoteProduto lote001, LoteProduto lote002, LoteProduto lote003) {
        //Fornecedores
        Fornecedor quimicaBrasil = salvarFornecedor("Química Brasil Ltda", "12.345.678/0001-90");
        Fornecedor farmoquimicaSul = salvarFornecedor("Farmoquímica Sul S.A.", "23.456.789/0001-01");
        Fornecedor embalagensPharma = salvarFornecedor("Embalagens Pharma Ltda", "34.567.890/0001-12");

        //Lotes de insumos
        LoteInsumo principioAtivo = salvarLoteInsumo("Paracetamol (princípio ativo)", "MP-QB-2026-001", LocalDate.now().plusYears(2), quimicaBrasil);
        LoteInsumo excipiente = salvarLoteInsumo("Amido de milho (excipiente)", "MP-FS-2026-014", LocalDate.now().plusYears(1), farmoquimicaSul);
        LoteInsumo estabilizante = salvarLoteInsumo("Estearato de magnésio (lubrificante)", "MP-FS-2026-022", LocalDate.now().plusMonths(18), farmoquimicaSul);
        LoteInsumo embalagem = salvarLoteInsumo("Blister PVC/alumínio (embalagem)", "EMB-EP-2026-105", LocalDate.now().plusYears(3), embalagensPharma);

        //Vínculo entre lotes de insumo e lotes de produto
        salvarConsumo(lote001, principioAtivo, 50.0);
        salvarConsumo(lote001, excipiente, 12.5);
        salvarConsumo(lote001, embalagem, 350.0);
        salvarConsumo(lote002, principioAtivo, 40.0);
        salvarConsumo(lote002, estabilizante, 8.0);
        salvarConsumo(lote002, embalagem, 280.0);
        salvarConsumo(lote003, excipiente, 20.0);

        //Controle de qualidade
        LocalDate fabricacao001 = lote001.getDataFabricacao();
        salvarAnalise(lote001, fabricacao001.plusDays(5), "APROVADO", "Ensaio físico-químico dentro da especificação.");
        salvarAnalise(lote001, fabricacao001.plusDays(8), "APROVADO", "Ensaio microbiológico sem contaminação.");
        salvarAnalise(lote002, lote002.getDataFabricacao().plusDays(5), "EM_ANALISE", "Aguardando laudo microbiológico.");

        //Destinos
        Destino farmaciaCentral = salvarDestino("Farmácia Central", "Rua da Consolação, 930 - São Paulo/SP");
        Destino hospitalSaoLucas = salvarDestino("Hospital São Lucas", "Av. Paulista, 1500 - São Paulo/SP");
        salvarDestino("Drogaria Popular Centro", "Rua XV de Novembro, 200 - Campinas/SP");

        //Expedições do lote aprovado
        Expedicao expedicaoFarmacia = salvarExpedicao(fabricacao001.plusDays(15), "NF-000123", farmaciaCentral);
        Expedicao expedicaoHospital = salvarExpedicao(fabricacao001.plusDays(20), "NF-000124", hospitalSaoLucas);
        salvarItemExpedicao(expedicaoFarmacia, lote001, 200, "CAIXA");
        salvarItemExpedicao(expedicaoHospital, lote001, 150, "CAIXA");

        //Histórico de status
        LocalDateTime inicio001 = fabricacao001.atTime(8, 0);
        salvarHistorico(lote001, null, StatusLote.EM_PRODUCAO, inicio001, "Início da produção.");
        salvarHistorico(lote001, StatusLote.EM_PRODUCAO, StatusLote.EM_QUARENTENA, inicio001.plusDays(3), "Produção concluída, lote enviado à quarentena.");
        salvarHistorico(lote001, StatusLote.EM_QUARENTENA, StatusLote.APROVADO, inicio001.plusDays(10), "Liberado pelo controle de qualidade.");
        salvarHistorico(lote001, StatusLote.APROVADO, StatusLote.EXPEDIDO, inicio001.plusDays(15), "Primeira expedição realizada.");

        LocalDateTime inicio002 = lote002.getDataFabricacao().atTime(8, 0);
        salvarHistorico(lote002, null, StatusLote.EM_PRODUCAO, inicio002, "Início da produção.");
        salvarHistorico(lote002, StatusLote.EM_PRODUCAO, StatusLote.EM_QUARENTENA, inicio002.plusDays(3), "Produção concluída, lote enviado à quarentena.");

        salvarHistorico(lote003, null, StatusLote.EM_PRODUCAO, lote003.getDataFabricacao().atTime(8, 0), "Início da produção.");

        lote001.setStatus(StatusLote.EXPEDIDO);
        repositoryManager.getLoteProdutoRepository().save(lote001);
    }

    private Fornecedor salvarFornecedor(String nome, String cnpj) {
        return repositoryManager.getFornecedorRepository().save(new Fornecedor(0, nome, cnpj));
    }

    private LoteInsumo salvarLoteInsumo(String nomeInsumo, String numeroLote, LocalDate validade, Fornecedor fornecedor) {
        return repositoryManager.getLoteInsumoRepository().save(new LoteInsumo(0, nomeInsumo, numeroLote, validade, fornecedor));
    }

    private void salvarConsumo(LoteProduto loteProduto, LoteInsumo loteInsumo, double quantidade) {
        repositoryManager.getConsumoInsumoRepository().save(new ConsumoInsumo(0, quantidade, loteProduto, loteInsumo));
    }

    private void salvarAnalise(LoteProduto lote, LocalDate dataAnalise, String resultado, String observacao) {
        repositoryManager.getAnaliseQualidadeRepository().save(new AnaliseQualidade(0, lote, dataAnalise, resultado, observacao));
    }

    private Destino salvarDestino(String nome, String endereco) {
        return repositoryManager.getDestinoRepository().save(new Destino(0, nome, endereco));
    }

    private Expedicao salvarExpedicao(LocalDate dataExpedicao, String notaFiscal, Destino destino) {
        return repositoryManager.getExpedicaoRepository().save(new Expedicao(0, dataExpedicao, notaFiscal, destino));
    }

    private void salvarItemExpedicao(Expedicao expedicao, LoteProduto lote, int quantidade, String unidadeMedida) {
        repositoryManager.getItemExpedicaoRepository().save(new ItemExpedicao(0, expedicao, lote, quantidade, unidadeMedida));
    }

    private void salvarHistorico(
            LoteProduto lote,
            StatusLote statusAnterior,
            StatusLote novoStatus,
            LocalDateTime data,
            String motivo
    ) {
        HistoricoStatus historico = new HistoricoStatus(0, lote, novoStatus, data, motivo);
        historico.setStatusAnterior(statusAnterior);
        repositoryManager.getHistoricoStatusRepository().save(historico);
    }

    private Produto obterOuCriarProduto(String nome, String descricao) {
        return repositoryManager.getProdutoRepository().findFirstByNome(nome)
                .orElseGet(() -> repositoryManager.getProdutoRepository().save(new Produto(0, nome, descricao)));
    }

    private LoteProduto obterOuCriarLote(
            String codigo,
            Produto produto,
            StatusLote status,
            LocalDate dataFabricacao,
            LocalDate validade
    ) {
        return repositoryManager.getLoteProdutoRepository().findByCodigoLote(codigo)
                .orElseGet(() -> repositoryManager.getLoteProdutoRepository().save(new LoteProduto(
                        0,
                        codigo,
                        dataFabricacao,
                        validade,
                        status,
                        produto
                )));
    }
}