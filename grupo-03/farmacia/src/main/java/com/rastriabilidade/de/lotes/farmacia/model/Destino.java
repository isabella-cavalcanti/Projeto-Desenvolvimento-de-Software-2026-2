package com.rastriabilidade.de.lotes.farmacia.model;

import jakarta.persistence.*;

@Entity
@Table(name = "destinos")
public class Destino {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;

    @Column(nullable = false, length = 150)
    private String nome;

    @Column(nullable = false, length = 500)
    private String endereco;

    public Destino() {}

    public Destino(
        int id, 
        String nome, 
        String endereco
    ) {
        this.id = id;
        this.nome = nome;
        this.endereco = endereco;
    }

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public String getNome() { return nome; }
    public void setNome(String nome) { this.nome = nome; }

    public String getEndereco() { return endereco; }
    public void setEndereco(String endereco) { this.endereco = endereco; }
}