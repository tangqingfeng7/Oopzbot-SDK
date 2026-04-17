"""Legacy API mixin backed by oopz_sdk."""

from oopz_sdk.client.sender import OopzSender as _CompatSender


class OopzApiMixin:
    """Compatibility mixin that forwards legacy oopz API methods to oopz_sdk."""


for _name, _value in vars(_CompatSender).items():
    if _name == "__init__" or _name.startswith("__"):
        continue
    setattr(OopzApiMixin, _name, _value)

del _name
del _value

__all__ = ["OopzApiMixin"]
