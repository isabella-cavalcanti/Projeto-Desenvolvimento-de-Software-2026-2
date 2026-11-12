package com.rastriabilidade.de.lotes.farmacia.repository;

import java.util.List;

import org.springframework.data.jpa.repository.EntityGraph;

import com.rastriabilidade.de.lotes.farmacia.interfaces.Repository;
import com.rastriabilidade.de.lotes.farmacia.model.ItemExpedicao;

public interface ItemExpedicaoRepository extends Repository<ItemExpedicao> {

    @EntityGraph(attributePaths = {"expedicao", "expedicao.destino"})
    List<ItemExpedicao> findByLoteProdutoIdOrderByExpedicaoDataExpedicaoAsc(int loteProdutoId);
}
