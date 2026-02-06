"""Core environment file management logic."""

import base64
import os
from pathlib import Path
from typing import Dict, List, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

from shared.logger import get_logger

logger = get_logger(__name__)


class EnvManager:
    """
    Manage environment files with encryption.

    Supports:
    - Encrypt/decrypt .env files
    - Switch between environments
    - Validate required variables
    - Diff environments
    """

    def __init__(self):
        """Initialize environment manager."""
        logger.debug("Initialized EnvManager")

    def load_env(self, filepath: Path) -> Dict[str, str]:
        """
        Load environment variables from file.

        Args:
            filepath: Path to .env file

        Returns:
            Dictionary of environment variables
        """
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        env_vars = {}

        with open(filepath, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse KEY=VALUE
                if "=" not in line:
                    logger.warning(f"Skipping invalid line {line_num}: {line}")
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value and value[0] in ['"', "'"] and value[-1] == value[0]:
                    value = value[1:-1]

                env_vars[key] = value

        logger.info(f"Loaded {len(env_vars)} variables from {filepath}")
        return env_vars

    def save_env(self, filepath: Path, env_vars: Dict[str, str]) -> None:
        """
        Save environment variables to file.

        Args:
            filepath: Path to .env file
            env_vars: Dictionary of environment variables
        """
        with open(filepath, "w") as f:
            for key, value in sorted(env_vars.items()):
                # Quote values with spaces
                if " " in value:
                    f.write(f'{key}="{value}"\n')
                else:
                    f.write(f"{key}={value}\n")

        logger.info(f"Saved {len(env_vars)} variables to {filepath}")

    def encrypt(self, filepath: Path, password: str, output_path: Optional[Path] = None) -> Path:
        """
        Encrypt environment file.

        Args:
            filepath: Path to .env file
            password: Encryption password
            output_path: Output path (defaults to input + .enc)

        Returns:
            Path to encrypted file
        """
        if output_path is None:
            output_path = Path(str(filepath) + ".enc")

        # Read original file
        with open(filepath, "rb") as f:
            data = f.read()

        # Derive key from password
        key = self._derive_key(password)
        fernet = Fernet(key)

        # Encrypt
        encrypted_data = fernet.encrypt(data)

        # Write encrypted file
        with open(output_path, "wb") as f:
            f.write(encrypted_data)

        logger.info(f"Encrypted {filepath} to {output_path}")
        return output_path

    def decrypt(self, filepath: Path, password: str, output_path: Optional[Path] = None) -> Path:
        """
        Decrypt environment file.

        Args:
            filepath: Path to encrypted .env file
            password: Decryption password
            output_path: Output path (defaults to input without .enc)

        Returns:
            Path to decrypted file
        """
        if output_path is None:
            output_path = Path(str(filepath).replace(".enc", ""))

        # Read encrypted file
        with open(filepath, "rb") as f:
            encrypted_data = f.read()

        # Derive key from password
        key = self._derive_key(password)
        fernet = Fernet(key)

        try:
            # Decrypt
            decrypted_data = fernet.decrypt(encrypted_data)

            # Write decrypted file
            with open(output_path, "wb") as f:
                f.write(decrypted_data)

            logger.info(f"Decrypted {filepath} to {output_path}")
            return output_path

        except Exception as e:
            raise ValueError(f"Decryption failed: {e}. Wrong password?")

    def _derive_key(self, password: str, salt: bytes = b"env-manager-salt") -> bytes:
        """
        Derive encryption key from password using PBKDF2.

        Args:
            password: User password
            salt: Salt for key derivation

        Returns:
            Derived key bytes
        """
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def validate(
        self,
        filepath: Path,
        required_vars: List[str],
    ) -> tuple[bool, List[str]]:
        """
        Validate that all required variables are present.

        Args:
            filepath: Path to .env file
            required_vars: List of required variable names

        Returns:
            Tuple of (is_valid, missing_vars)
        """
        env_vars = self.load_env(filepath)
        missing = [var for var in required_vars if var not in env_vars]

        is_valid = len(missing) == 0
        return (is_valid, missing)

    def diff(self, file1: Path, file2: Path) -> Dict[str, tuple]:
        """
        Compare two environment files.

        Args:
            file1: First .env file
            file2: Second .env file

        Returns:
            Dict of differences: {key: (value1, value2)}
        """
        env1 = self.load_env(file1)
        env2 = self.load_env(file2)

        all_keys = set(env1.keys()) | set(env2.keys())

        differences = {}
        for key in sorted(all_keys):
            val1 = env1.get(key)
            val2 = env2.get(key)

            if val1 != val2:
                differences[key] = (val1, val2)

        return differences

    def merge(
        self,
        base_file: Path,
        override_file: Path,
        output_file: Path,
    ) -> Dict[str, str]:
        """
        Merge two environment files.

        Args:
            base_file: Base .env file
            override_file: Override .env file
            output_file: Output .env file

        Returns:
            Merged environment variables
        """
        base_env = self.load_env(base_file)
        override_env = self.load_env(override_file)

        # Merge (override takes precedence)
        merged = {**base_env, **override_env}

        # Save
        self.save_env(output_file, merged)

        logger.info(f"Merged {base_file} + {override_file} → {output_file}")
        return merged
