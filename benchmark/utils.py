"""Utility functions for benchmarking."""


def format_size(size_bytes: int) -> str:
    """Format size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.0f}MB"


def get_missing_tests(provider_results: list) -> dict:
    """Find tests that are missing for some providers.

    Returns dict mapping (operation, file_size) to list of providers missing that test.
    """
    # Collect all unique test combinations
    all_tests = set()
    provider_tests = {}

    for provider_result in provider_results:
        provider_name = provider_result.provider_name
        provider_tests[provider_name] = set()

        for result in provider_result.results:
            test_key = (result.operation, result.file_size)
            all_tests.add(test_key)
            provider_tests[provider_name].add(test_key)

    # Find missing tests
    missing = {}
    for test_key in all_tests:
        missing_providers = []
        for provider_name, tests in provider_tests.items():
            if test_key not in tests:
                missing_providers.append(provider_name)

        if missing_providers:
            missing[test_key] = missing_providers

    return missing
