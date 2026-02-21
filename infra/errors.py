"""Custom exceptions for Jarvis Pi."""


class JarvisError(Exception):
    """Base class for recoverable Jarvis errors."""


class HealthCheckFailed(JarvisError):
    """Raised when startup health checks fail."""
