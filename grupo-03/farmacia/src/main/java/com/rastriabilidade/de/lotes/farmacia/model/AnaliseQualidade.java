package com.rastriabilidade.de.lotes.farmacia.model;

import jakarta.persistence.*;
import java.time.LocalDate;

@Entity
@Table(name = "analises_qualidade")
public class AnaliseQualidade {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "lote_produto_id", nullable = false)
    private LoteProduto lote;

    private LocalDate dataAnalise;

    @Column(nullable = false, length = 60)
    private String resultado;

    @Column(length = 1000)
    private String observacao;

    public AnaliseQualidade() {}

    public AnaliseQualidade(
        int id, 
        LoteProduto lote,
        LocalDate dataAnalise,                    
        String resultado, 
        String observacao
    ) {
        this.id = id;
        this.lote = lote;
        this.dataAnalise = dataAnalise;
        this.resultado = resultado;
        this.observacao = observacao;
    }

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public LoteProduto getLote() { return lote; }
    public void setLote(LoteProduto lote) { this.lote = lote; }

    public LocalDate getDataAnalise() { return dataAnalise; }
    public void setDataAnalise(LocalDate dataAnalise) { this.dataAnalise = dataAnalise; }

    public String getResultado() { return resultado; }
    public void setResultado(String resultado) { this.resultado = resultado; }

    public String getObservacao() { return observacao; }
    public void setObservacao(String observacao) { this.observacao = observacao; }
}