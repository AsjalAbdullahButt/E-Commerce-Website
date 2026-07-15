"""Test utilities"""
import pytest
from utils.helpers import hash_password, verify_password


class TestHelpers:
    """Tests for utility functions"""
    
    def test_password_hashing(self):
        """Verify password hashing and verification"""
        password = "TestPassword123!"
        hashed = hash_password(password)
        
        # Verify hashed password is different from plain
        assert hashed != password
        
        # Verify password matches hash
        assert verify_password(password, hashed)
        
        # Verify wrong password fails
        assert not verify_password("WrongPassword", hashed)
    
    def test_password_hash_consistency(self):
        """Verify password hashing is consistent"""
        password = "TestPassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Different hashes (bcrypt uses random salt)
        assert hash1 != hash2
        
        # Both verify correctly
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)
