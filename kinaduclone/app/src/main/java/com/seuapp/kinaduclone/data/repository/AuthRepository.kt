package com.seuapp.kinaduclone.data.repository

import com.google.firebase.auth.FirebaseAuth

class AuthRepository {

    private val auth = FirebaseAuth.getInstance()

    fun login(email: String, senha: String, onResult: (Boolean) -> Unit) {
        auth.signInWithEmailAndPassword(email, senha)
            .addOnCompleteListener {
                onResult(it.isSuccessful)
            }
    }

    fun logout() {
        auth.signOut()
    }

    fun getUserId(): String? {
        return auth.currentUser?.uid
    }
}
