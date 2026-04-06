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


class EndpointDeprecatedError(ApiError):
    """412 — Owner API endpoint unavailable for this VIN.

    This can mean:
    1. Vehicle not yet delivered (not linked to account)
    2. Modern VIN that requires Fleet API (LRW/7SA/XP7 prefixes)

    Use is_likely_pre_delivery() to distinguish.
    """

    def __init__(self, message: str = "") -> None:
        detail = message or (
            "Vehicle not accessible via Owner API.\n"
            "If your vehicle hasn't been delivered yet, this is normal — "
            "live data will be available after delivery.\n"
            "If already delivered, switch to Fleet API:\n"
            "  tesla config set backend fleet && tesla config auth fleet"
        )
        super().__init__(412, detail)


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


class DockerNotFoundError(TeslaCliError):
    """Docker or docker compose not available."""

    def __init__(self, detail: str = "") -> None:
        msg = "Docker is required but not found."
        if detail:
            msg += f" {detail}"
        super().__init__(msg)


class TeslaMateStackError(TeslaCliError):
    """Error managing the TeslaMate Docker stack."""


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
