"""
Security middleware for enhanced authentication and protection
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Set
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Enhanced security middleware"""
    
    def __init__(self, app, rate_limit_requests: int = 100, rate_limit_window: int = 60):
        super().__init__(app)
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window = rate_limit_window
        self.request_counts: Dict[str, Dict] = {}
        self.blocked_ips: Set[str] = set()
        
    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = self.get_client_ip(request)
        
        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "IP temporarily blocked due to suspicious activity"}
            )
        
        # Rate limiting
        if not self.check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"}
            )
        
        # Security headers check
        self.add_security_headers(request)
        
        # Process request
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add security headers to response
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log suspicious activity
        if process_time > 5.0:  # Slow requests might indicate attacks
            logger.warning(f"Slow request from {client_ip}: {request.url} took {process_time:.2f}s")
        
        return response
    
    def get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded headers (when behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """Check rate limiting for client IP"""
        now = time.time()
        window_start = now - self.rate_limit_window
        
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []
        
        # Clean old requests
        self.request_counts[client_ip] = [
            req_time for req_time in self.request_counts[client_ip]
            if req_time > window_start
        ]
        
        # Check if limit exceeded
        if len(self.request_counts[client_ip]) >= self.rate_limit_requests:
            # Block IP temporarily if severely exceeding limits
            if len(self.request_counts[client_ip]) > self.rate_limit_requests * 2:
                self.blocked_ips.add(client_ip)
                # Remove block after 1 hour (in production, use Redis with TTL)
                # This is simplified for demo
            return False
        
        # Record this request
        self.request_counts[client_ip].append(now)
        return True
    
    def add_security_headers(self, request: Request):
        """Add security-related request processing"""
        # Check for suspicious patterns in URL
        suspicious_patterns = [
            '../', '..\\', '<script', 'javascript:', 'vbscript:',
            'onload=', 'onerror=', 'eval(', 'exec(', 'system(',
            'union select', 'drop table', 'insert into'
        ]
        
        url_path = str(request.url).lower()
        for pattern in suspicious_patterns:
            if pattern in url_path:
                logger.warning(f"Suspicious URL pattern detected: {pattern} in {request.url}")
                break


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Authentication-specific middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.protected_paths = {
            '/auth/me', '/auth/logout', '/auth/change-password',
            '/realtime/', '/dm/', '/message/'
        }
        self.public_paths = {
            '/auth/login', '/auth/register', '/auth/refresh',
            '/docs', '/redoc', '/openapi.json', '/health', '/'
        }
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Skip middleware for public paths
        if any(path.startswith(public_path) for public_path in self.public_paths):
            return await call_next(request)
        
        # Check if path requires authentication
        requires_auth = any(path.startswith(protected_path) for protected_path in self.protected_paths)
        
        if requires_auth:
            # Check for Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Authentication required"},
                    headers={"WWW-Authenticate": "Bearer"}
                )
        
        return await call_next(request)


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.safe_methods = {"GET", "HEAD", "OPTIONS", "TRACE"}
    
    async def dispatch(self, request: Request, call_next):
        # Skip CSRF check for safe methods
        if request.method in self.safe_methods:
            return await call_next(request)
        
        # Skip for API endpoints (assuming API uses tokens, not cookies)
        if request.url.path.startswith("/api/") or request.url.path.startswith("/auth/"):
            return await call_next(request)
        
        # In a full implementation, you'd check CSRF tokens here
        return await call_next(request)