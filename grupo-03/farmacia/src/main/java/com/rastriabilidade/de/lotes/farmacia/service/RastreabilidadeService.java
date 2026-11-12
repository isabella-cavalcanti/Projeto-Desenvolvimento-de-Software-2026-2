package com.rastriabilidade.de.lotes.farmacia.service;

import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.rastriabilidade.de.lotes.farmacia.exception.LoteNaoEncontradoException;
import com.rastriabilidade.de.lotes.farmacia.manager.RepositoryManager;
import com.rastriabilidade.de.lotes.farmacia.model.AnaliseQualidade;
import com.rastriabilidade.de.lotes.farmacia.model.ConsumoInsumo;
import com.rastriabilidade.de.lotes.farmacia.model.Destino;
import com.rastriabilidade.de.lotes.farmacia.model.Expedicao;
import com.rastriabilidade.de.lotes.farmacia.model.HistoricoStatus;
import com.rastriabilidade.de.lotes.farmacia.model.ItemExpedicao;
import com.rastriabilidade.de.lotes.farmacia.model.LoteInsumo;
import com.rastriabilidade.de.lotes.farmacia.model.LoteProduto;

@Service
public class RastreabilidadeService {

    private static final DateTimeFormatter FORMATO_DATA = DateTimeFormatter.ofPattern("dd/MM/yyyy");
    private static final DateTimeFormatter FORMATO_DATA_HORA = DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm");
    private static final DateTimeFormatter FORMATO_ORDENACAO = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");
    private static final int TAMANHO_PREFIXO = 16;

    private final RepositoryManager manager;

    public RastreabilidadeService(RepositoryManager manager) {
        this.manager = manager;
    }

    @Transactional(readOnly = true)
    public LoteProduto buscarLotePorCodigo(String codigoLote) {
        if (codigoLote == null || codigoLote.isBlank()) {
            throw new IllegalArgumentException("O código do lote é obrigatório!");
        }

        return manager.getLoteProdutoRepository().findByCodigoLote(codigoLote.trim())
            .orElseThrow(() -> new LoteNaoEncontradoException(
                    "Lote não encontrado: " + codigoLote
            ));
    }

    @Transactional(readOnly = true)
    public LoteProduto consultarInformacoes(String codigoLote) {
        return buscarLotePorCodigo(codigoLote);
    }

    @Transactional(readOnly = true)
    public List<ConsumoInsumo> consultarOrigem(String codigoLote) {
        LoteProduto lote = buscarLotePorCodigo(codigoLote);
        return manager.getConsumoInsumoRepository().findByLoteProdutoId(lote.getId());
    }

    @Transactional(readOnly = true)
    public List<ItemExpedicao> consultarDestino(String codigoLote) {
        LoteProduto lote = buscarLotePorCodigo(codigoLote);
        return manager.getItemExpedicaoRepository().findByLoteProdutoIdOrderByExpedicaoDataExpedicaoAsc(lote.getId());
    }

    @Transactional(readOnly = true)
    public String rastrearLote(String codigoLote) {
        LoteProduto lote = buscarLotePorCodigo(codigoLote);

        List<String> linhaDoTempo = new ArrayList<>();
        LocalDateTime dataFabricacao = lote.getDataFabricacao().atStartOfDay();

        adicionarEvento(linhaDoTempo, dataFabricacao,
                  "\nFABRICAÇÃO | Data: " + formatarData(dataFabricacao)
              + "\n           | Lote: " + lote.getCodigoLote()
              + "\n           | Produto: " + lote.getProduto().getNome());

        for (ConsumoInsumo consumo : manager.getConsumoInsumoRepository().findByLoteProdutoId(lote.getId())) {
            LoteInsumo loteInsumo = consumo.getLoteInsumo();
            adicionarEvento(linhaDoTempo, dataFabricacao,
                      "\nINSUMO | Data: " + formatarData(dataFabricacao)
                  + "\n       | Insumo: " + loteInsumo.getNomeInsumo()
                  + "\n       | Lote: " + loteInsumo.getNumeroLote()
                  + "\n       | Fornecedor: " + loteInsumo.getFornecedor().getNome()
                  + "\n       | Quantidade: " + consumo.getQuantidade());
        }

        for (HistoricoStatus historico : lote.getHistoricos()) {
            String anterior = historico.getStatusAnterior() == null ? "INÍCIO" : historico.getStatusAnterior().name();
            adicionarEvento(linhaDoTempo, historico.getData(),
                      "\nSTATUS | Data: " + formatarData(historico.getData())
                  + "\n       | Alteração: " + anterior + " -> " + historico.getNovoStatus().name()
                  + campoOpcional("\n       | Motivo: ", historico.getMotivo()));
        }

        for (AnaliseQualidade analise : manager.getAnaliseQualidadeRepository().findByLoteIdOrderByDataAnaliseAsc(lote.getId())) {
            LocalDateTime dataAnalise = analise.getDataAnalise().atStartOfDay();
            adicionarEvento(linhaDoTempo, dataAnalise,
                      "\nQUALIDADE | Data: " + formatarData(dataAnalise)
                  + "\n          | Resultado: " + analise.getResultado()
                  + campoOpcional("\n          | Observação: ", analise.getObservacao()));
        }

        for (ItemExpedicao item : manager.getItemExpedicaoRepository()
                .findByLoteProdutoIdOrderByExpedicaoDataExpedicaoAsc(lote.getId())) {
            Expedicao expedicao = item.getExpedicao();
            Destino destino = expedicao.getDestino();
            LocalDateTime dataExpedicao = expedicao.getDataExpedicao().atStartOfDay();
            adicionarEvento(linhaDoTempo, dataExpedicao,
                      "\nEXPEDIÇÃO | Data: " + formatarData(dataExpedicao)
                  + "\n          | Nome do Local: " + destino.getNome()
                  + "\n          | Endereço: " + destino.getEndereco()
                  + "\n          | Quantidade: " + item.getQuantidade() + " " + item.getUnidadeMedida()
                  + "\n          | NF: " + expedicao.getNotaFiscal());
        }

        linhaDoTempo.sort(Comparator.comparing(bloco -> bloco.substring(0, TAMANHO_PREFIXO)));

        String cabecalho = "\nRASTREAMENTO DO LOTE | Lote: " + lote.getCodigoLote()
                       + "\n                     | Produto: " + lote.getProduto().getNome()
                       + "\n                     | Status atual: " + lote.getStatus().name()
                       + "\n                     | Validade: " + lote.getValidade().format(FORMATO_DATA);

        List<String> blocos = linhaDoTempo.stream()
                .map(bloco -> bloco.substring(TAMANHO_PREFIXO))
                .toList();

        return cabecalho + "\n\n" + String.join("\n\n", blocos);
    }

    private static void adicionarEvento(List<String> linhaDoTempo, LocalDateTime data, String bloco) {
        linhaDoTempo.add(data.format(FORMATO_ORDENACAO) + bloco);
    }

    private static String formatarData(LocalDateTime data) {
        return data.toLocalTime().equals(LocalTime.MIDNIGHT)
                ? data.format(FORMATO_DATA)
                : data.format(FORMATO_DATA_HORA);
    }

    private static String campoOpcional(String rotulo, String valor) {
        return valor == null || valor.isBlank() ? "" : rotulo + valor;
    }
}