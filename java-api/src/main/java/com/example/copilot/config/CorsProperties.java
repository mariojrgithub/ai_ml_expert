package com.example.copilot.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Configures the allowed CORS origins for the API.
 *
 * Set ALLOWED_ORIGINS as a comma-separated list of origins, e.g.:
 *   ALLOWED_ORIGINS=http://localhost:8501,https://app.example.com
 *
 * Defaults to http://localhost:8501 (the local Streamlit UI) when not specified.
 */
@Component
@ConfigurationProperties(prefix = "cors")
public class CorsProperties {

    private List<String> allowedOrigins = List.of("http://localhost:8501");

    public List<String> getAllowedOrigins() {
        return allowedOrigins;
    }

    public void setAllowedOrigins(List<String> allowedOrigins) {
        this.allowedOrigins = allowedOrigins;
    }
}
