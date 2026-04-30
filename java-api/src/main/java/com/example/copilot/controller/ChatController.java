package com.example.copilot.controller;
import com.example.copilot.dto.ChatRequest;
import com.example.copilot.dto.ChatResponse;
import com.example.copilot.service.AgentGatewayService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api")
@Tag(name = "Chat", description = "Send messages to the engineering copilot agent")
@SecurityRequirement(name = "bearerAuth")
public class ChatController {
    
private final AgentGatewayService agentGatewayService;

    public ChatController(AgentGatewayService agentGatewayService) {
        this.agentGatewayService = agentGatewayService;
    }

    @PostMapping("/chat")
    @Operation(summary = "Send a message", description = "Sends a user message to the agent and returns a full response.")
    @ApiResponse(responseCode = "200", description = "Successful response from agent")
    @ApiResponse(responseCode = "400", description = "Validation error")
    @ApiResponse(responseCode = "401", description = "Unauthorized – provide a valid Bearer token")
    public Mono<ResponseEntity<ChatResponse>> chat(@Valid @RequestBody ChatRequest request) {
        return agentGatewayService.chat(request)
                .map(ResponseEntity::ok);
    }

    @PostMapping(value = "/chat/stream", produces = "text/event-stream")
    @Operation(summary = "Stream a response", description = "Streams the agent response as Server-Sent Events.")
    @ApiResponse(responseCode = "200", description = "SSE stream")
    @ApiResponse(responseCode = "401", description = "Unauthorized – provide a valid Bearer token")
    public Flux<String> chatStream(@Valid @RequestBody ChatRequest request) {
        return agentGatewayService.chatStream(request);
    }
}
