package com.example.copilot.controller;

import com.example.copilot.config.JwtProperties;
import com.example.copilot.dto.LoginRequest;
import com.example.copilot.dto.LoginResponse;
import com.example.copilot.security.JwtUtil;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.ReactiveAuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/auth")
@Tag(name = "Authentication", description = "Obtain and manage JWT tokens")
public class AuthController {

    private final ReactiveAuthenticationManager authManager;
    private final JwtUtil jwtUtil;
    private final JwtProperties jwtProperties;

    public AuthController(ReactiveAuthenticationManager authManager,
                          JwtUtil jwtUtil,
                          JwtProperties jwtProperties) {
        this.authManager = authManager;
        this.jwtUtil = jwtUtil;
        this.jwtProperties = jwtProperties;
    }

    @PostMapping("/login")
    @Operation(summary = "Authenticate and receive a JWT",
               description = "Provide valid credentials to receive a Bearer token for subsequent requests.")
    @ApiResponse(responseCode = "200", description = "Login successful")
    @ApiResponse(responseCode = "401", description = "Invalid credentials")
    public Mono<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        return authManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.username(), request.password()))
                .map(auth -> new LoginResponse(
                        jwtUtil.generateToken(auth.getName()),
                        jwtProperties.getExpirationMs()))
                .onErrorMap(ex -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid credentials"));
    }
}
