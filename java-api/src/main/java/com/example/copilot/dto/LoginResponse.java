package com.example.copilot.dto;

public record LoginResponse(String token, String tokenType, long expiresInMs) {
    public LoginResponse(String token, long expiresInMs) {
        this(token, "Bearer", expiresInMs);
    }
}
