package com.seuapp.kinaduclone.ui.home

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.seuapp.kinaduclone.R
import com.seuapp.kinaduclone.data.repository.AtividadeRepository
import com.seuapp.kinaduclone.ui.atividade.AtividadeAdapter

class HomeActivity : AppCompatActivity() {

    private lateinit var recycler: RecyclerView
    private val repository = AtividadeRepository()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_home)

        recycler = findViewById(R.id.recyclerAtividades)
        recycler.layoutManager = LinearLayoutManager(this)

        carregarAtividades()
    }

    private fun carregarAtividades() {
        repository.getAtividades { lista ->
            recycler.adapter = AtividadeAdapter(lista)
        }
    }
}
