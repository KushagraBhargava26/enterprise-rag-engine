import pytest
import jwt
from packages.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

def test_password_hashing():
    raw_password = "super-secret-password-123"
    hashed = hash_password(raw_password)
    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("wrong-password", hashed) is False

def test_jwt_token_lifecycle():
    user_payload = {"sub": "user-uuid-123", "email": "test@enterprise.com"}
    token = create_access_token(user_payload)
    assert isinstance(token, str)

    decoded = decode_access_token(token)
    assert decoded["sub"] == user_payload["sub"]
    assert decoded["email"] == user_payload["email"]
    assert "exp" in decoded
    assert "iat" in decoded

def test_invalid_jwt_token():
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("invalid.token.string")
