"""Legacy-style API mixin exposed from oopz_sdk."""

from oopz_sdk.client.rest import OopzRESTClient


class OopzApiMixin:
    """Mixin exposing the REST client API surface for direct reuse."""


for _name, _value in vars(OopzRESTClient).items():
    if _name == "__init__" or _name.startswith("__"):
        continue
    setattr(OopzApiMixin, _name, _value)

del _name
del _value

__all__ = ["OopzApiMixin"]
