package com.example.copilot.security;

import org.springframework.core.env.Environment;
import org.springframework.security.core.userdetails.ReactiveUserDetailsService;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import reactor.core.publisher.Mono;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * In-memory user store. Replace with a database-backed implementation
 * (e.g. R2DBC UserRepository) for production use.
 *
 * Requires ADMIN_USER and ADMIN_PASS to be present in the Spring Environment
 * (environment variables or test property sources). Fails fast at startup if
 * either is missing or blank.
 */
@Service
public class InMemoryUserDetailsService implements ReactiveUserDetailsService {

    private final Map<String, UserDetails> users = new ConcurrentHashMap<>();

    public InMemoryUserDetailsService(PasswordEncoder passwordEncoder, Environment env) {
        String adminUser = env.getProperty("ADMIN_USER");
        String adminPass = env.getProperty("ADMIN_PASS");

        if (!StringUtils.hasText(adminUser)) {
            throw new IllegalStateException(
                    "ADMIN_USER environment variable is required but was not set.");
        }
        if (!StringUtils.hasText(adminPass)) {
            throw new IllegalStateException(
                    "ADMIN_PASS environment variable is required but was not set.");
        }

        users.put(adminUser, User.withUsername(adminUser)
                .password(passwordEncoder.encode(adminPass))
                .roles("ADMIN", "USER")
                .build());
    }

    @Override
    public Mono<UserDetails> findByUsername(String username) {
        UserDetails user = users.get(username);
        return user != null ? Mono.just(user) : Mono.empty();
    }
}
