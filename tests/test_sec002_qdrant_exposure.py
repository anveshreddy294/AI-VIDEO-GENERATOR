"""Tests for SEC-002: Qdrant Network Isolation and Secret Precedence."""

from pathlib import Path
import yaml
import pytest


def test_qdrant_docker_compose_security():
    compose_path = Path(__file__).resolve().parent.parent / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml must exist"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})
    assert "qdrant" in services, "qdrant service must be defined"
    assert "api" in services, "api service must be defined"

    qdrant = services["qdrant"]
    api = services["api"]

    # 1. Assert no host ports are published on Qdrant
    assert "ports" not in qdrant or not qdrant["ports"], (
        "Qdrant must not publish ports to host interfaces (must be internal to Docker network)"
    )

    # 2. Assert Qdrant image is pinned and not using :latest
    qdrant_image = qdrant.get("image", "")
    assert ":latest" not in qdrant_image, f"Qdrant image must be pinned, got '{qdrant_image}'"
    assert "qdrant/qdrant:" in qdrant_image, "Expected official Qdrant image"

    # 3. Assert API service targets internal network
    api_env = api.get("environment", [])
    if isinstance(api_env, list):
        env_dict = {}
        for item in api_env:
            if "=" in item:
                k, v = item.split("=", 1)
                env_dict[k] = v
    else:
        env_dict = api_env or {}

    assert env_dict.get("QDRANT_URL") == "http://qdrant:6333", (
        "API must communicate with Qdrant via internal network name 'http://qdrant:6333'"
    )

    # 4. Assert QDRANT_API_KEY is not forcibly emptied in environment
    assert "QDRANT_API_KEY" not in env_dict or env_dict.get("QDRANT_API_KEY") != "", (
        "docker-compose must not overwrite QDRANT_API_KEY with empty string"
    )
