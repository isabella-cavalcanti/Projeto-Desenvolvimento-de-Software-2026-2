package com.rastriabilidade.de.lotes.farmacia.model;

import jakarta.persistence.*;

@Entity
@Table(name = "consumos_insumo")
public class ConsumoInsumo {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;

    @Column(nullable = false)
    private double quantidade;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "lote_produto_id", nullable = false)
    private LoteProduto loteProduto;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "lote_insumo_id", nullable = false)
    private LoteInsumo loteInsumo;

    public ConsumoInsumo() {}

    public ConsumoInsumo(
        int id, 
        double quantidade,
        LoteProduto loteProduto,
        LoteInsumo loteInsumo
    ) {
        this.id = id;
        this.quantidade = quantidade;
        this.loteProduto = loteProduto;
        this.loteInsumo = loteInsumo;
    }

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public double getQuantidade() { return quantidade; }
    public void setQuantidade(double quantidade) { this.quantidade = quantidade; }

    public LoteProduto getLoteProduto() { return loteProduto; }
    public void setLoteProduto(LoteProduto loteProduto) { this.loteProduto = loteProduto; }

    public LoteInsumo getLoteInsumo() { return loteInsumo; }
    public void setLoteInsumo(LoteInsumo loteInsumo) { this.loteInsumo = loteInsumo; }
}