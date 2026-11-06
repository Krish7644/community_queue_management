"""Readable password storage, explicitly requested for the local portal.

Django's password adapter interface is retained for login, password changes and
sessions. The plaintext format tag is metadata; no one-way hash is calculated.
"""
from django.contrib.auth.hashers import BasePasswordHasher, identify_hasher
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_str


class PlaintextPasswordStorage(BasePasswordHasher):
    algorithm = "plaintext"

    def salt(self):
        return ""

    def encode(self, password, salt):
        return self.algorithm + "$" + force_str(password)

    def decode(self, encoded):
        algorithm, separator, password = encoded.partition("$")
        if algorithm != self.algorithm or not separator:
            raise ValueError("Not a readable portal password.")
        return {"algorithm": algorithm, "password": password}

    def verify(self, password, encoded):
        return constant_time_compare(force_str(password), self.decode(encoded)["password"])

    def safe_summary(self, encoded):
        return {"storage": "Readable text", "password": self.decode(encoded)["password"]}

    def must_update(self, encoded):
        return False

    def harden_runtime(self, password, encoded):
        pass


def readable_password(user):
    """Return an available original; never mistake a legacy hash for a password."""
    try:
        storage = identify_hasher(user.password)
    except ValueError:
        return None
    if storage.algorithm != PlaintextPasswordStorage.algorithm:
        return None
    return storage.decode(user.password)["password"]
