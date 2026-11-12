package com.rastriabilidade.de.lotes.farmacia.model;

import java.time.LocalDate;
import java.util.List;

import com.rastriabilidade.de.lotes.farmacia.enuns.StatusLote;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;

@Entity
@Table(name = "lotes_produto")
public class LoteProduto {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private int id;

	@Column(nullable = false, unique = true, length = 60)
	private String codigoLote;
	private LocalDate dataFabricacao;
	private LocalDate validade;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 30)
	private StatusLote status;

	@ManyToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "produto_id", nullable = false)
	private Produto produto;

	@OneToMany(mappedBy = "loteProduto")
	private List<ConsumoInsumo> insumosConsumidos;

	@OneToMany(mappedBy = "lote")
	private List<AnaliseQualidade> analises;

	@OneToMany(mappedBy = "loteProduto")
	private List<ItemExpedicao> itensExpedicao;

	@OneToMany(mappedBy = "lote") 
	@OrderBy("data ASC") 
	private List<HistoricoStatus> historicos;

	public LoteProduto() {}

	public LoteProduto(
		int id, 
		String codigoLote,
	    LocalDate dataFabricacao,
	    LocalDate validade,
	    StatusLote status,
	    Produto produto
	) {
		this.id = id;
		this.codigoLote = codigoLote;
		this.dataFabricacao = dataFabricacao;
		this.validade = validade;
		this.status = status;
		this.produto = produto;
	}

	public int getId() { return id; }
	public void setId(int id) { this.id = id; }

	public String getCodigoLote() { return codigoLote; }
	public void setCodigoLote(String codigoLote) { this.codigoLote = codigoLote; }

	public LocalDate getDataFabricacao() { return dataFabricacao; }
	public void setDataFabricacao(LocalDate dataFabricacao) { this.dataFabricacao = dataFabricacao; }

	public LocalDate getValidade() { return validade; }
	public void setValidade(LocalDate validade) { this.validade = validade; }

	public StatusLote getStatus() { return status; }
	public void setStatus(StatusLote status) { this.status = status; }

	public Produto getProduto() { return produto; }
	public void setProduto(Produto produto) { this.produto = produto; }

	public List<ConsumoInsumo> getInsumosConsumidos() { return insumosConsumidos; }
	public void setInsumosConsumidos(List<ConsumoInsumo> insumosConsumidos) { this.insumosConsumidos = insumosConsumidos; }

	public List<AnaliseQualidade> getAnalises() { return analises; }
	public void setAnalises(List<AnaliseQualidade> analises) { this.analises = analises; }

	public List<ItemExpedicao> getItensExpedicao() { return itensExpedicao; }
	public void setItensExpedicao(List<ItemExpedicao> itensExpedicao) { this.itensExpedicao = itensExpedicao; }

	public List<HistoricoStatus> getHistoricos() { return historicos; }
	public void setHistoricos(List<HistoricoStatus> historicos) { this.historicos = historicos; }
}