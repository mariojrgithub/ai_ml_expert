package com.example.copilot.controller;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.AutoConfigureWebTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
@AutoConfigureWebTestClient
@TestPropertySource(properties = {
        "ADMIN_USER=testadmin",
        "ADMIN_PASS=TestPass123!"
})
class AuthControllerTest {

    @Autowired
    private WebTestClient webTestClient;

    @Test
    void loginSuccess_returnsToken() {
        webTestClient.post().uri("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"username\":\"testadmin\",\"password\":\"TestPass123!\"}")
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.token").isNotEmpty()
                .jsonPath("$.tokenType").isEqualTo("Bearer")
                .jsonPath("$.expiresInMs").isEqualTo(3600000);
    }

    @Test
    void loginFailure_returns401() {
        webTestClient.post().uri("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"username\":\"testadmin\",\"password\":\"wrongpassword\"}")
                .exchange()
                .expectStatus().isUnauthorized();
    }

    @Test
    void loginMissingFields_returns400() {
        webTestClient.post().uri("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"username\":\"\",\"password\":\"\"}")
                .exchange()
                .expectStatus().isBadRequest();
    }
}
