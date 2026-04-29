package com.example.copilot.controller;
import com.example.copilot.dto.ChatRequest;
import com.example.copilot.dto.ChatResponse;
import com.example.copilot.service.AgentGatewayService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api")
public class ChatController {
    
private final AgentGatewayService agentGatewayService;

    public ChatController(AgentGatewayService agentGatewayService) {
        this.agentGatewayService = agentGatewayService;
    }

    @PostMapping("/chat")
    public Mono<ResponseEntity<ChatResponse>> chat(@Valid @RequestBody ChatRequest request) {
        return agentGatewayService.chat(request)
                .map(ResponseEntity::ok);
    }

    @PostMapping(value = "/chat/stream", produces = "application/x-ndjson")
    public Flux<String> chatStream(@Valid @RequestBody ChatRequest request) {
        return agentGatewayService.chatStream(request);
    }
}
