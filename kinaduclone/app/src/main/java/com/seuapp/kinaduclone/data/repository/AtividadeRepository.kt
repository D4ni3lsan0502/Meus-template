package com.seuapp.kinaduclone.data.repository

import com.google.firebase.firestore.FirebaseFirestore
import com.seuapp.kinaduclone.data.model.Atividade

class AtividadeRepository {

    private val db = FirebaseFirestore.getInstance()

    fun getAtividades(onResult: (List<Atividade>) -> Unit) {
        db.collection("atividades")
            .get()
            .addOnSuccessListener { result ->
                val lista = result.map { it.toObject(Atividade::class.java) }
                onResult(lista)
            }
    }
}
