"""Custom exceptions for Jarvis Pi."""


class JarvisError(Exception):
    """Base class for recoverable Jarvis errors."""


class HealthCheckFailed(JarvisError):
    """Raised when startup health checks fail."""


class CameraDisconnectedError(JarvisError):
    """Raised for transient camera disconnects."""


class LLMServiceError(JarvisError):
    """Raised for transient LLM API failures or timeouts."""


class AudioDeviceUnavailableError(JarvisError):
    """Raised when microphone or speaker device initialization fails."""
