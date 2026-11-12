package com.rastriabilidade.de.lotes.farmacia.repository;

import java.util.Optional;

import org.springframework.data.jpa.repository.EntityGraph;

import com.rastriabilidade.de.lotes.farmacia.interfaces.Repository;
import com.rastriabilidade.de.lotes.farmacia.model.LoteProduto;

public interface LoteProdutoRepository extends Repository<LoteProduto> {

	@EntityGraph(attributePaths = {"produto"})
	Optional<LoteProduto> findByCodigoLote(String codigoLote);
}
