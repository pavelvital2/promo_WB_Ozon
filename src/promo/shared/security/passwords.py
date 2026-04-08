from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Protocol


class PasswordHasher(Protocol):
    def hash_password(self, password: str) -> str: ...

    def verify_password(self, password: str, password_hash: str) -> bool: ...


@dataclass(slots=True, frozen=True)
class ScryptPasswordHasher:
    salt_size: int = 16
    n: int = 2**14
    r: int = 8
    p: int = 1
    dklen: int = 64

    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(self.salt_size)
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=self.n,
            r=self.r,
            p=self.p,
            dklen=self.dklen,
        )
        return "$".join(
            [
                "scrypt",
                f"n={self.n},r={self.r},p={self.p},dklen={self.dklen}",
                base64.urlsafe_b64encode(salt).decode("ascii"),
                base64.urlsafe_b64encode(digest).decode("ascii"),
            ]
        )

    def verify_password(self, password: str, password_hash: str) -> bool:
        algorithm, parameters, encoded_salt, encoded_digest = password_hash.split("$", 3)
        if algorithm != "scrypt":
            return False
        config = {key: int(value) for key, value in (part.split("=") for part in parameters.split(","))}
        salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
        expected = base64.urlsafe_b64decode(encoded_digest.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=config["n"],
            r=config["r"],
            p=config["p"],
            dklen=config["dklen"],
        )
        return hmac.compare_digest(actual, expected)

