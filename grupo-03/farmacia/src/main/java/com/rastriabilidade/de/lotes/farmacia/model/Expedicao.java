package com.rastriabilidade.de.lotes.farmacia.model;

import jakarta.persistence.*;
import java.time.LocalDate;
import java.util.List;

@Entity
@Table(name = "expedicoes")
public class Expedicao {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;
    private LocalDate dataExpedicao;
    private String notaFiscal;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "destino_id", nullable = false)
    private Destino destino;

    @OneToMany(mappedBy = "expedicao")
    private List<ItemExpedicao> itens;

    public Expedicao() {}

    public Expedicao(
        int id, 
        LocalDate dataExpedicao,
        String notaFiscal, 
        Destino destino
    ) {
        this.id = id;
        this.dataExpedicao = dataExpedicao;
        this.notaFiscal = notaFiscal;
        this.destino = destino;
    }

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public LocalDate getDataExpedicao() { return dataExpedicao; }
    public void setDataExpedicao(LocalDate dataExpedicao) { this.dataExpedicao = dataExpedicao; }

    public String getNotaFiscal() { return notaFiscal; }
    public void setNotaFiscal(String notaFiscal) { this.notaFiscal = notaFiscal; }

    public Destino getDestino() { return destino; }
    public void setDestino(Destino destino) { this.destino = destino; }

    public List<ItemExpedicao> getItens() { return itens; }
    public void setItens(List<ItemExpedicao> itens) { this.itens = itens; }
}