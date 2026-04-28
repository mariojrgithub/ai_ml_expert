package com.example.copilot.dto;

import java.util.List;
import java.util.Map;

public record ChatResponse(
        String executionId,
        String intent,
        String format,
        String content,
        String language,
        List<String> warnings,
        List<Map<String, Object>> citations
) {
}