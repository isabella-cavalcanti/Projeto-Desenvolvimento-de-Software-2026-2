package com.rastriabilidade.de.lotes.farmacia.model;

import com.rastriabilidade.de.lotes.farmacia.enuns.StatusLote;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "historico_status")
public class HistoricoStatus {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "lote_produto_id", nullable = false)
    private LoteProduto lote;

    @Enumerated(EnumType.STRING)
    @Column(length = 30)
    private StatusLote statusAnterior;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private StatusLote novoStatus;

    @Column(name = "data_historico", nullable = false)
    private LocalDateTime data;

    @Column(length = 1000)
    private String motivo;

    public HistoricoStatus() {}

    public HistoricoStatus(
        int id, 
        LoteProduto lote,
        StatusLote novoStatus, 
        LocalDateTime data,
        String motivo
    ) {
        this.id = id;
        this.lote = lote;
        this.statusAnterior = lote.getStatus();
        this.novoStatus = novoStatus;
        this.data = data;
        this.motivo = motivo;
    }

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public LoteProduto getLote() { return lote; }
    public void setLote(LoteProduto lote) { this.lote = lote; }

    public StatusLote getStatusAnterior() { return statusAnterior; }
    public void setStatusAnterior(StatusLote statusAnterior) { this.statusAnterior = statusAnterior; }

    public StatusLote getNovoStatus() { return novoStatus; }
    public void setNovoStatus(StatusLote novoStatus) { this.novoStatus = novoStatus; }

    public LocalDateTime getData() { return data; }
    public void setData(LocalDateTime data) { this.data = data; }

    public String getMotivo() { return motivo; }
    public void setMotivo(String motivo) { this.motivo = motivo; }
}
