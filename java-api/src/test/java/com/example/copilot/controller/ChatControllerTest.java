package com.example.copilot.controller;

import com.example.copilot.dto.ChatResponse;
import com.example.copilot.service.AgentGatewayService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.WebFluxTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Flux;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@WebFluxTest(ChatController.class)
class ChatControllerTest {

    @Autowired
    private WebTestClient webTestClient;

    @MockBean
    private AgentGatewayService agentGatewayService;

    @Test
    void shouldForwardChatRequest() {
        when(agentGatewayService.chat(any()))
                .thenReturn(new ChatResponse(
                        "exec-1",
                        "CODE",
                        "code",
                        "print('hi')",
                        "python",
                        List.of(),
                        List.of()
                ));

        webTestClient.post().uri("/api/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"sessionId\":\"s1\",\"message\":\"write python code\"}")
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.executionId").isEqualTo("exec-1")
                .jsonPath("$.intent").isEqualTo("CODE")
                .jsonPath("$.content").isEqualTo("print('hi')")
                .jsonPath("$.format").isEqualTo("code");
    }

    @Test
    void shouldStreamChatResponse() {
        when(agentGatewayService.chatStream(any()))
                .thenReturn(Flux.just(
                        "{\"type\":\"meta\",\"format\":\"markdown\",\"language\":null,\"intent\":\"QA\"}",
                        "{\"type\":\"delta\",\"content\":\"Hello\"}",
                        "{\"type\":\"done\",\"warnings\":[],\"citations\":[]}"
                ));

        webTestClient.post().uri("/api/chat/stream")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"sessionId\":\"s1\",\"message\":\"What are CI/CD guardrails?\"}")
                .exchange()
                .expectStatus().isOk()
                .expectHeader().contentTypeCompatibleWith(MediaType.TEXT_EVENT_STREAM)
                .returnResult(String.class)
                .getResponseBody()
                .as(body -> {
                    var frames = body.collectList().block();
                    assert frames != null && frames.size() == 3;
                    return frames;
                });
    }
}