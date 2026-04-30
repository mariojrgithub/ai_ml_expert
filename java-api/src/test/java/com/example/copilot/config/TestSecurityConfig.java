package com.example.copilot.config;

import com.example.copilot.security.JwtUtil;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.security.core.userdetails.ReactiveUserDetailsService;
import reactor.core.publisher.Mono;

/**
 * Provides the security infrastructure beans that are not in a @WebFluxTest slice.
 * Import this into any controller test that needs the security filter chain to load.
 */
@TestConfiguration
public class TestSecurityConfig {

    @Bean
    public JwtProperties jwtProperties() {
        JwtProperties props = new JwtProperties();
        props.setSecret("test-secret-key-for-unit-tests-32chars!!");
        props.setExpirationMs(3_600_000L);
        return props;
    }

    @Bean
    public JwtUtil jwtUtil(JwtProperties jwtProperties) {
        return new JwtUtil(jwtProperties);
    }

    @Bean
    public ReactiveUserDetailsService reactiveUserDetailsService() {
        // No real users needed in controller-layer tests
        return username -> Mono.empty();
    }
}
