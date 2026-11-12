package com.rastriabilidade.de.lotes.farmacia.repository;

import com.rastriabilidade.de.lotes.farmacia.interfaces.Repository;
import com.rastriabilidade.de.lotes.farmacia.model.Produto;

import java.util.Optional;

public interface ProdutoRepository extends Repository<Produto> {

	Optional<Produto> findFirstByNome(String nome);
}
