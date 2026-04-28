package com.example.copilot.controller;
import com.example.copilot.dto.ChatRequest;
import com.example.copilot.dto.ChatResponse;
import com.example.copilot.service.AgentGatewayService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/api")
public class ChatController {
    private final AgentGatewayService agentGatewayService;
    public ChatController(AgentGatewayService agentGatewayService) { this.agentGatewayService = agentGatewayService; }
    @PostMapping("/chat")
    public ResponseEntity<ChatResponse> chat(@Valid @RequestBody ChatRequest request) { return ResponseEntity.ok(agentGatewayService.chat(request)); }
}