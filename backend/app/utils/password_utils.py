"""
Password utilities for secure password generation.

Uses the secrets module for cryptographically secure random generation.
"""
import secrets
import string


def generate_secure_password(length: int = 14) -> str:
    """
    Generate a cryptographically secure password.

    Guarantees at least:
    - 1 uppercase letter
    - 1 lowercase letter
    - 2 digits
    - 2 special characters

    Args:
        length: Password length (minimum 8, default 14)

    Returns:
        Secure random password string
    """
    if length < 8:
        length = 8

    # Character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*"

    # Guarantee minimum requirements
    password_chars = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(digits),
        secrets.choice(special),
        secrets.choice(special),
    ]

    # Fill remaining length with random characters from all sets
    all_chars = uppercase + lowercase + digits + special
    remaining_length = length - len(password_chars)

    for _ in range(remaining_length):
        password_chars.append(secrets.choice(all_chars))

    # Shuffle to randomize position of guaranteed characters
    secrets.SystemRandom().shuffle(password_chars)

    return ''.join(password_chars)
