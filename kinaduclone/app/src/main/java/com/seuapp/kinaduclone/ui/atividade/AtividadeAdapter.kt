package com.seuapp.kinaduclone.ui.atividade

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.seuapp.kinaduclone.R
import com.seuapp.kinaduclone.data.model.Atividade

class AtividadeAdapter(
    private val lista: List<Atividade>
) : RecyclerView.Adapter<AtividadeAdapter.ViewHolder>() {

    class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val titulo: TextView = view.findViewById(R.id.tvTitulo)
        val descricao: TextView = view.findViewById(R.id.tvDescricao)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_atividade, parent, false)
        return ViewHolder(view)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val atividade = lista[position]
        holder.titulo.text = atividade.titulo
        holder.descricao.text = atividade.descricao
    }

    override fun getItemCount() = lista.size
}
