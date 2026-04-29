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

    
private final WebClient agentWebClient;

    public AgentGatewayService(WebClient agentWebClient) {
        this.agentWebClient = agentWebClient;
    }

    public Mono<ChatResponse> chat(ChatRequest request) {
        return agentWebClient.post()
                .uri("/agent/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(ChatResponse.class)
                .timeout(Duration.ofSeconds(300));
    }

    public Flux<String> chatStream(ChatRequest request) {
        return agentWebClient.post()
                .uri("/agent/chat/stream")
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.valueOf("application/x-ndjson"))
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(String.class);
    }
}
