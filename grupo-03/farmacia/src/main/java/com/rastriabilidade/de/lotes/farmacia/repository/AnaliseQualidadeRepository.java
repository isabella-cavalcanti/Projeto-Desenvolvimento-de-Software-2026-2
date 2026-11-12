package com.rastriabilidade.de.lotes.farmacia.repository;

import java.util.List;

import com.rastriabilidade.de.lotes.farmacia.interfaces.Repository;
import com.rastriabilidade.de.lotes.farmacia.model.AnaliseQualidade;

public interface AnaliseQualidadeRepository extends Repository<AnaliseQualidade> {

    List<AnaliseQualidade> findByLoteIdOrderByDataAnaliseAsc(int loteId);
}
