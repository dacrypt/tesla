"""Exception hierarchy for tesla-cli."""


class TeslaCliError(Exception):
    """Base exception for all tesla-cli errors."""


class AuthenticationError(TeslaCliError):
    """Token expired, invalid, or missing."""


class ConfigurationError(TeslaCliError):
    """Missing or invalid configuration."""


class VehicleAsleepError(TeslaCliError):
    """Vehicle is asleep; wake it first."""


class ApiError(TeslaCliError):
    """HTTP error from Tesla/Tessie API."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class RateLimitError(ApiError):
    """429 Too Many Requests."""

    def __init__(self, message: str = "Rate limited, try again later"):
        super().__init__(429, message)


class OrderNotFoundError(TeslaCliError):
    """Order RN not found or API endpoint broken."""


class ExternalToolNotFoundError(TeslaCliError):
    """A required external binary/tool was not found on PATH.

    Raised by L0/L3 wrappers when the underlying binary (e.g. tesla-control)
    is not installed.
    """

    def __init__(self, tool_name: str, install_hint: str = "") -> None:
        self.tool_name = tool_name
        self.install_hint = install_hint
        msg = f"External tool `{tool_name}` not found on PATH."
        if install_hint:
            msg += f"\nInstall: {install_hint}"
        super().__init__(msg)


class BackendNotSupportedError(TeslaCliError):
    """Feature not available on the current vehicle backend.

    Raised by default base-class implementations of Fleet-only methods
    when called on backends that don't support them (Owner API, Tessie).
    """

    def __init__(self, feature: str, backends: str = "fleet") -> None:
        self.feature = feature
        self.backends = backends
        super().__init__(
            f"`{feature}` is not available on this backend.\n"
            f"Switch to the {backends} backend:  tesla config set backend {backends}\n"
            f"(see `tesla config --help` for setup instructions)"
        )
