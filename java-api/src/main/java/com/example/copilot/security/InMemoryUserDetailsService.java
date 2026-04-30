package com.example.copilot.security;

import org.springframework.security.core.userdetails.ReactiveUserDetailsService;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * In-memory user store. Replace with a database-backed implementation
 * (e.g. R2DBC UserRepository) for production use.
 */
@Service
public class InMemoryUserDetailsService implements ReactiveUserDetailsService {

    private final Map<String, UserDetails> users = new ConcurrentHashMap<>();

    public InMemoryUserDetailsService(PasswordEncoder passwordEncoder) {
        // Seed a default admin user – override via environment variables in production.
        String adminUser = System.getenv().getOrDefault("ADMIN_USER", "admin");
        String adminPass = System.getenv().getOrDefault("ADMIN_PASS", "changeme");
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
