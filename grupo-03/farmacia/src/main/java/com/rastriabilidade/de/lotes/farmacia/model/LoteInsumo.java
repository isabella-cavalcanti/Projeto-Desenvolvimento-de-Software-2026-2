package com.rastriabilidade.de.lotes.farmacia.model;

import java.time.LocalDate;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "lotes_insumo")
public class LoteInsumo {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;

    @Column(nullable = false, length = 120)
    private String nomeInsumo;

    @Column(nullable = false, length = 60)
    private String numeroLote;
    private LocalDate validade;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "fornecedor_id", nullable = false)
    private Fornecedor fornecedor;

    public LoteInsumo() {}

    public LoteInsumo(
        int id, 
        String nomeInsumo,
        String numeroLote, 
        LocalDate validade, 
        Fornecedor fornecedor
    ) {
        this.id = id;
        this.nomeInsumo = nomeInsumo;
        this.numeroLote = numeroLote;
        this.validade = validade;
        this.fornecedor = fornecedor;
    }

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public String getNomeInsumo() { return nomeInsumo; }
    public void setNomeInsumo(String nomeInsumo) { this.nomeInsumo = nomeInsumo; }

    public String getNumeroLote() { return numeroLote; }
    public void setNumeroLote(String numeroLote) { this.numeroLote = numeroLote; }

    public LocalDate getValidade() { return validade; }
    public void setValidade(LocalDate validade) { this.validade = validade; }

    public Fornecedor getFornecedor() { return fornecedor; }
    public void setFornecedor(Fornecedor fornecedor) { this.fornecedor = fornecedor; }
}