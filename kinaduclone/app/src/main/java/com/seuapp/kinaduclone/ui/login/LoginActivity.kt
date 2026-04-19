package com.seuapp.kinaduclone.ui.login

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.seuapp.kinaduclone.ui.home.HomeActivity
import com.seuapp.kinaduclone.data.repository.AuthRepository

class LoginActivity : AppCompatActivity() {

    private val authRepository = AuthRepository()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Aqui você liga com layout XML depois

        val email = "teste@email.com"
        val senha = "123456"

        authRepository.login(email, senha) { sucesso ->
            if (sucesso) {
                startActivity(Intent(this, HomeActivity::class.java))
                finish()
            }
        }
    }
}
