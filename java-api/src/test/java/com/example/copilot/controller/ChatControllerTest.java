package com.example.copilot.controller;

import com.example.copilot.dto.ChatResponse;
import com.example.copilot.service.AgentGatewayService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(ChatController.class)
class ChatControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private AgentGatewayService agentGatewayService;

    @Test
    void shouldForwardChatRequest() throws Exception {
        when(agentGatewayService.chat(any()))
                .thenReturn(new ChatResponse(
                        "exec-1",
                        "CODE",
                        "CODE\nprint('hi')",
                        List.of(),
                        List.of()
                ));

        mockMvc.perform(
                    post("/api/chat")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"sessionId\":\"s1\",\"message\":\"write python code\"}")
                )
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.executionId").value("exec-1"))
                .andExpect(jsonPath("$.intent").value("CODE"));
    }
}