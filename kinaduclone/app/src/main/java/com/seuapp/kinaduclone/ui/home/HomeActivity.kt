package com.seuapp.kinaduclone.ui.home

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.seuapp.kinaduclone.data.repository.AtividadeRepository

class HomeActivity : AppCompatActivity() {

    private val repository = AtividadeRepository()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        repository.getAtividades { lista ->
            lista.forEach {
                println(it.titulo)
            }
        }
    }
}
