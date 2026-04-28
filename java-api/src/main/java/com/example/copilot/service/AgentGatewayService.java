package com.example.copilot.service;

import com.example.copilot.dto.ChatRequest;
import com.example.copilot.dto.ChatResponse;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

@Service
public class AgentGatewayService {

    private final WebClient agentWebClient;

    public AgentGatewayService(WebClient agentWebClient) {
        this.agentWebClient = agentWebClient;
    }

    public ChatResponse chat(ChatRequest request) {
        return agentWebClient.post()
                .uri("/agent/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(ChatResponse.class)
                .block();
    }
}