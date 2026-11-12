package com.rastriabilidade.de.lotes.farmacia.controller;

import java.util.List;
import java.util.Scanner;

import org.springframework.stereotype.Component;
import org.springframework.boot.CommandLineRunner;

import com.rastriabilidade.de.lotes.farmacia.exception.LoteNaoEncontradoException;
import com.rastriabilidade.de.lotes.farmacia.model.ConsumoInsumo;
import com.rastriabilidade.de.lotes.farmacia.model.Expedicao;
import com.rastriabilidade.de.lotes.farmacia.model.ItemExpedicao;
import com.rastriabilidade.de.lotes.farmacia.model.LoteProduto;
import com.rastriabilidade.de.lotes.farmacia.service.RastreabilidadeService;

@Component

public class ConsoleController implements CommandLineRunner{

    private final RastreabilidadeService service;

    public ConsoleController(RastreabilidadeService service) {
        this.service = service;
    }
    
    @Override
    public void run(String... args) {
        menu();
    }

    private void menu() {
        Scanner tcd = new Scanner(System.in);
        int opcao;
        
        do {
            System.out.println("\nMENU | 1. Consultar Lote");
            System.out.println("     | 2. Origem do Lote");
            System.out.println("     | 3. Destino do Lote");
            System.out.println("     | 4. Rastrear Lote");
            System.out.println("     | 0. Sair");
            System.out.print("Escolha uma opção: ");

            try {
                opcao = Integer.parseInt(tcd.nextLine());
            } catch (NumberFormatException e) {
                opcao = -1;
            }

            opcoesMenu(opcao, tcd);

        } while (opcao != 0);
    }

    private void opcoesMenu(int opcao, Scanner tcd) {
        try {
            switch (opcao) {
                case 1:
                    LoteProduto lote = service.consultarInformacoes(lerCodigoLote("Consultar Lote", tcd));
                    System.out.println("\nINFORMAÇÕES DO LOTE | Lote: " + lote.getCodigoLote()
                                   + "\n                    | Produto: " + lote.getProduto().getNome()
                                   + "\n                    | Status: " + lote.getStatus()
                                   + "\n                    | Fabricação: " + lote.getDataFabricacao()
                                   + "\n                    | Validade: " + lote.getValidade());
                    break;
                case 2:
                    for (ConsumoInsumo c : service.consultarOrigem(lerCodigoLote("Origem do Lote", tcd))) {
                        System.out.println("\nORIGEM | Insumo: " + c.getLoteInsumo().getNomeInsumo()
                                       + "\n       | Lote: " + c.getLoteInsumo().getNumeroLote()
                                       + "\n       | Fornecedor: " + c.getLoteInsumo().getFornecedor().getNome()
                                       + "\n       | Quantidade: " + c.getQuantidade());
                    }
                    break;
                case 3: {
                    String codigoLote = lerCodigoLote("Destino do Lote", tcd);
                    List<ItemExpedicao> itens = service.consultarDestino(codigoLote);

                    if (itens.isEmpty()) {
                        System.out.println("Nenhuma expedição registrada para o lote " + codigoLote + "!\n");
                    } else {
                        for (ItemExpedicao item : itens) {
                            Expedicao expedicao = item.getExpedicao();
                            System.out.println("\nDESTINO | Lote: " + codigoLote.trim()
                                           + "\n        | Nome do Local: " + expedicao.getDestino().getNome()
                                           + "\n        | Endereço: " + expedicao.getDestino().getEndereco()
                                           + "\n        | Data da Expedição: " + expedicao.getDataExpedicao()
                                           + "\n        | Quantidade: " + item.getQuantidade() + " " + item.getUnidadeMedida()
                                           + "\n        | NF: " + expedicao.getNotaFiscal());
                        }
                    }
                    break;
                }
                case 4:
                    System.out.println(service.rastrearLote(lerCodigoLote("Rastrear Lote", tcd)));
                    break;
                case 0:
                    System.out.println("Encerrando...");
                    break;
                default:
                    System.out.println("Opção inválida! Tente novamente!");
                    break;
            }
        } catch (LoteNaoEncontradoException | IllegalArgumentException e) {
            System.out.println(e.getMessage());
        }
    }

    private String lerCodigoLote(String msg, Scanner tcd) {
        System.out.print("\n"+ msg + " | Informe o código do lote: ");
        return tcd.nextLine();
    }

}
