package com.example.copilot.dto;

import java.util.List;

public record ChatResponse(
        String executionId,
        String intent,
        String format,
        String content,
        String language,
        List<String> warnings,
        List<CitationDto> citations
) {
}