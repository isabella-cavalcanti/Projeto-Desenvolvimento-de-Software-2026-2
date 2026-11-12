package com.rastriabilidade.de.lotes.farmacia.model;

import jakarta.persistence.*;
import jakarta.persistence.Table;

@Entity
@Table(name = "itens_expedicao")
public class ItemExpedicao {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "expedicao_id", nullable = false)
    private Expedicao expedicao;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "lote_produto_id", nullable = false)
    private LoteProduto loteProduto;

    @Column(nullable = false)
    private int quantidade;

    @Column(nullable = false, length = 20)
    private String unidadeMedida;

    public ItemExpedicao() {}

    public ItemExpedicao(
            int id,
            Expedicao expedicao,
            LoteProduto loteProduto,
            int quantidade,
            String unidadeMedida
    ) {
        this.id = id;
        this.expedicao = expedicao;
        this.loteProduto = loteProduto;
        this.quantidade = quantidade;
        this.unidadeMedida = unidadeMedida;
    }

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public Expedicao getExpedicao() { return expedicao; }
    public void setExpedicao(Expedicao expedicao) { this.expedicao = expedicao; }

    public LoteProduto getLoteProduto() { return loteProduto; }
    public void setLoteProduto(LoteProduto loteProduto) { this.loteProduto = loteProduto; }

    public int getQuantidade() { return quantidade; }
    public void setQuantidade(int quantidade) { this.quantidade = quantidade; }

    public String getUnidadeMedida() { return unidadeMedida; }
    public void setUnidadeMedida(String unidadeMedida) { this.unidadeMedida = unidadeMedida; }
}