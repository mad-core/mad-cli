"""``.env`` editing use cases: get / set / unset with validation and masking.

The general-purpose ``.env`` editor behind ``mad config`` and the
``/v1/instances/{name}/config`` routes. Each takes an already-resolved
:class:`Instance`. A handful of known keys are validated on write; compose-baked
keys (host port / data bind) still write to ``.env`` but the adapter warns that a
regenerate is required. Secret-looking values are masked on read via
:class:`~mad_cli.core.usecases.instances.EnvItem`.
"""

from __future__ import annotations

from collections.abc import Callable

from mad_cli.core.instance import Instance
from mad_cli.core.keyspec import is_secret_key
from mad_cli.core.usecases.errors import NotFoundError, ValidationError
from mad_cli.core.usecases.instances import EnvItem

# Keys whose value was rendered into compose.yml at install time.
COMPOSE_KEYS: tuple[str, ...] = ("MAD_HOST_PORT", "MAD_DATA_PATH")


def _validate_port(value: str) -> str:
    try:
        port = int(value)
    except ValueError:
        raise ValidationError(f"invalid MAD_HOST_PORT {value!r}: must be an integer") from None
    if not 1 <= port <= 65535:
        raise ValidationError(f"invalid MAD_HOST_PORT {value!r}: must be between 1 and 65535")
    return str(port)


def _validate_timeout(value: str) -> str:
    try:
        seconds = int(value)
    except ValueError:
        raise ValidationError(
            f"invalid MAD_AGENT_TIMEOUT_S {value!r}: must be an integer"
        ) from None
    if seconds <= 0:
        raise ValidationError(f"invalid MAD_AGENT_TIMEOUT_S {value!r}: must be a positive integer")
    return str(seconds)


_VALIDATORS: dict[str, Callable[[str], str]] = {
    "MAD_HOST_PORT": _validate_port,
    "MAD_AGENT_TIMEOUT_S": _validate_timeout,
}


def _item(key: str, value: str) -> EnvItem:
    return EnvItem(key=key, value=value, secret=is_secret_key(key))


def list_config(instance: Instance) -> list[EnvItem]:
    """Return all ``.env`` items (values masked on display)."""
    env = instance.env
    return [_item(key, env.get(key) or "") for key in env.keys()]  # noqa: SIM118


def get_config(instance: Instance, key: str) -> EnvItem:
    """Return one ``.env`` item. Raises :class:`NotFoundError` when unset."""
    value = instance.env.get(key)
    if value is None:
        raise NotFoundError(f"{key} is not set on {instance.name}")
    return _item(key, value)


def set_config(instance: Instance, key: str, value: str) -> tuple[EnvItem, bool]:
    """Validate and write a ``.env`` value.

    Returns ``(item, compose_baked)`` where ``compose_baked`` is True for keys
    rendered into compose.yml at install time. Raises :class:`ValidationError` for
    a bad known value.
    """
    validator = _VALIDATORS.get(key)
    if validator is not None:
        value = validator(value)
    instance.env.set(key, value)
    instance.env.save()
    return _item(key, value), key in COMPOSE_KEYS


def unset_config(instance: Instance, key: str) -> bool:
    """Remove ``key`` from the instance's ``.env``.

    Returns whether the key existed; False is a no-op the adapter reports.
    """
    if instance.env.get(key) is None:
        return False
    instance.env.unset(key)
    instance.env.save()
    return True
