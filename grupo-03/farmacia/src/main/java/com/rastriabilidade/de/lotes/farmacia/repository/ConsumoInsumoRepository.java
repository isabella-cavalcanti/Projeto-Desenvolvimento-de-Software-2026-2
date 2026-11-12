package com.rastriabilidade.de.lotes.farmacia.repository;

import java.util.List;

import org.springframework.data.jpa.repository.EntityGraph;

import com.rastriabilidade.de.lotes.farmacia.interfaces.Repository;
import com.rastriabilidade.de.lotes.farmacia.model.ConsumoInsumo;

public interface ConsumoInsumoRepository extends Repository<ConsumoInsumo> {

    @EntityGraph(attributePaths = {"loteInsumo", "loteInsumo.fornecedor"})
    List<ConsumoInsumo> findByLoteProdutoId(int loteProdutoId);
}
