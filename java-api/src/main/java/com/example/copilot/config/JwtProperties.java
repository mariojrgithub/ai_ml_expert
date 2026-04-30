package com.example.copilot.config;

import jakarta.annotation.PostConstruct;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

@Component
@ConfigurationProperties(prefix = "security.jwt")
public class JwtProperties {

    private static final int MIN_SECRET_LENGTH = 32;

    private String secret;
    private long expirationMs;

    /** Fail fast at startup if the JWT secret is absent or too short. */
    @PostConstruct
    public void validate() {
        if (!StringUtils.hasText(secret)) {
            throw new IllegalStateException(
                    "security.jwt.secret (JWT_SECRET) is required but was not set.");
        }
        if (secret.length() < MIN_SECRET_LENGTH) {
            throw new IllegalStateException(
                    "security.jwt.secret must be at least " + MIN_SECRET_LENGTH
                    + " characters. Current length: " + secret.length());
        }
    }

    public String getSecret() { return secret; }
    public void setSecret(String secret) { this.secret = secret; }

    public long getExpirationMs() { return expirationMs; }
    public void setExpirationMs(long expirationMs) { this.expirationMs = expirationMs; }
}
