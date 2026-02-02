"""Configuration management using TOML."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

try:
    import tomllib
except ImportError:
    import tomli as tomllib


@dataclass
class ProviderConfig:
    """Configuration for a single storage provider."""

    name: str
    type: Literal["s3", "local"]
    enabled: bool

    # S3-specific fields
    endpoint: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    bucket: str | None = None
    region: str | None = None

    # Local-specific fields
    base_path: str | None = None

    def validate(self) -> None:
        """Validate provider configuration."""
        if self.type == "s3":
            if not all([self.endpoint, self.access_key, self.secret_key, self.bucket]):
                raise ValueError(
                    f"S3 provider '{self.name}' missing required fields: "
                    f"endpoint, access_key, secret_key, bucket"
                )
        elif self.type == "local":
            if not self.base_path:
                raise ValueError(f"Local provider '{self.name}' missing required field: base_path")


@dataclass
class BenchmarkConfig:
    """Global benchmark configuration."""

    test_prefix: str = "benchmark-test"
    default_workers: int = 10
    cleanup_after: bool = True
    runs_per_test: int = 3
    max_retries: int = 5
    timeout_seconds: int = 300


@dataclass
class Config:
    """Complete configuration."""

    benchmark: BenchmarkConfig
    providers: list[ProviderConfig]

    @classmethod
    def from_file(cls, config_path: str | Path = "config.toml") -> "Config":
        """Load configuration from TOML file."""
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Copy config.toml.example to config.toml and edit it with your credentials."
            )

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Parse benchmark config
        benchmark_data = data.get("benchmark", {})
        benchmark_config = BenchmarkConfig(
            test_prefix=benchmark_data.get("test_prefix", "benchmark-test"),
            default_workers=benchmark_data.get("default_workers", 10),
            cleanup_after=benchmark_data.get("cleanup_after", True),
            runs_per_test=benchmark_data.get("runs_per_test", 3),
            max_retries=benchmark_data.get("max_retries", 5),
            timeout_seconds=benchmark_data.get("timeout_seconds", 300),
        )

        # Parse provider configs
        providers = []
        for provider_data in data.get("providers", []):
            provider = ProviderConfig(
                name=provider_data["name"],
                type=provider_data["type"],
                enabled=provider_data.get("enabled", True),
                endpoint=provider_data.get("endpoint"),
                access_key=provider_data.get("access_key"),
                secret_key=provider_data.get("secret_key"),
                bucket=provider_data.get("bucket"),
                region=provider_data.get("region"),
                base_path=provider_data.get("base_path"),
            )
            providers.append(provider)

        return cls(benchmark=benchmark_config, providers=providers)

    def get_enabled_providers(self) -> list[ProviderConfig]:
        """Get list of enabled providers."""
        return [p for p in self.providers if p.enabled]

    def get_provider(self, name: str) -> ProviderConfig | None:
        """Get provider by name."""
        for provider in self.providers:
            if provider.name == name:
                return provider
        return None

    def validate(self) -> None:
        """Validate all enabled providers."""
        for provider in self.get_enabled_providers():
            provider.validate()
