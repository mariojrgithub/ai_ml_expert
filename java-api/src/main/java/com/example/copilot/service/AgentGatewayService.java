package com.example.copilot.service;

import com.example.copilot.dto.ChatRequest;
import com.example.copilot.dto.ChatResponse;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.time.Duration;


@Service
public class AgentGatewayService {

    private static final String CORRELATION_HEADER = "X-Correlation-ID";

private final WebClient agentWebClient;

    public AgentGatewayService(WebClient agentWebClient) {
        this.agentWebClient = agentWebClient;
    }

    public Mono<ChatResponse> chat(ChatRequest request, String correlationId) {
        return agentWebClient.post()
                .uri("/agent/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .header(CORRELATION_HEADER, correlationId)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(ChatResponse.class)
                .timeout(Duration.ofSeconds(300));
    }

    public Flux<String> chatStream(ChatRequest request, String correlationId) {
        return agentWebClient.post()
                .uri("/agent/chat/stream")
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.valueOf("application/x-ndjson"))
                .header(CORRELATION_HEADER, correlationId)
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(String.class)
                // StringDecoder already splits on \n; just drop any blank lines that
                // arrive as SSE separators or keep-alive frames.
                .filter(line -> !line.isBlank());
    }
}
