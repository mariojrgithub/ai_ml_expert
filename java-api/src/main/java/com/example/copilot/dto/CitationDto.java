package com.example.copilot.dto;

public record CitationDto(
        String source,
        String title,
        String snippet,
        Double similarity,
        Double rerankScore,
        String url
) {
}
