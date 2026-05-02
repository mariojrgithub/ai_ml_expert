package com.example.copilot.controller;
import com.example.copilot.dto.ChatRequest;
import com.example.copilot.dto.ChatResponse;
import com.example.copilot.service.AgentGatewayService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.UUID;

@RestController
@RequestMapping("/api")
@Tag(name = "Chat", description = "Send messages to the engineering copilot agent")
@SecurityRequirement(name = "bearerAuth")
public class ChatController {

    private static final Logger log = LoggerFactory.getLogger(ChatController.class);
    private static final String CORRELATION_HEADER = "X-Correlation-ID";

    private final AgentGatewayService agentGatewayService;

    public ChatController(AgentGatewayService agentGatewayService) {
        this.agentGatewayService = agentGatewayService;
    }

    @PostMapping("/chat")
    @Operation(summary = "Send a message", description = "Sends a user message to the agent and returns a full response.")
    @ApiResponse(responseCode = "200", description = "Successful response from agent")
    @ApiResponse(responseCode = "400", description = "Validation error")
    @ApiResponse(responseCode = "401", description = "Unauthorized – provide a valid Bearer token")
    public Mono<ResponseEntity<ChatResponse>> chat(
            @Valid @RequestBody ChatRequest request,
            @RequestHeader(value = CORRELATION_HEADER, required = false) String correlationId) {
        String cid = (correlationId != null && !correlationId.isBlank()) ? correlationId : UUID.randomUUID().toString();
        log.info("[{}] POST /api/chat", cid);
        return agentGatewayService.chat(request, cid)
                .map(ResponseEntity::ok);
    }

    @PostMapping(value = "/chat/stream", produces = "text/event-stream")
    @Operation(summary = "Stream a response", description = "Streams the agent response as Server-Sent Events.")
    @ApiResponse(responseCode = "200", description = "SSE stream")
    @ApiResponse(responseCode = "401", description = "Unauthorized – provide a valid Bearer token")
    public Flux<String> chatStream(
            @Valid @RequestBody ChatRequest request,
            @RequestHeader(value = CORRELATION_HEADER, required = false) String correlationId) {
        String cid = (correlationId != null && !correlationId.isBlank()) ? correlationId : UUID.randomUUID().toString();
        log.info("[{}] POST /api/chat/stream", cid);
        return agentGatewayService.chatStream(request, cid);
    }
}
