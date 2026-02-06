"""CLI interface for Environment File Manager."""

import sys
from pathlib import Path
from typing import Optional

import click

from shared.cli import create_table, error, handle_errors, info, print_table, success, warning
from shared.logger import setup_logger

from .manager import EnvManager


@click.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--encrypt",
    "-e",
    is_flag=True,
    help="Encrypt the file",
)
@click.option(
    "--decrypt",
    "-d",
    is_flag=True,
    help="Decrypt the file",
)
@click.option(
    "--password",
    "-p",
    prompt=True,
    hide_input=True,
    help="Encryption/decryption password",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path",
)
@click.option(
    "--validate",
    "-v",
    multiple=True,
    help="Validate required variables",
)
@click.option(
    "--diff",
    type=click.Path(exists=True, path_type=Path),
    help="Compare with another .env file",
)
@click.option("--verbose", is_flag=True, help="Verbose output")
@handle_errors
def main(
    file: Path,
    encrypt: bool,
    decrypt: bool,
    password: str,
    output: Optional[Path],
    validate: tuple,
    diff: Optional[Path],
    verbose: bool,
):
    """
    Environment File Manager - Manage .env files securely.

    Examples:

        \b
        # Encrypt .env file
        env-manager .env.prod --encrypt --password secret

        \b
        # Decrypt .env file
        env-manager .env.prod.enc --decrypt --password secret

        \b
        # Validate required variables
        env-manager .env --validate DATABASE_URL --validate API_KEY

        \b
        # Compare two environments
        env-manager .env.dev --diff .env.prod
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logger(__name__, level=log_level)

    manager = EnvManager()

    # Encrypt
    if encrypt:
        try:
            output_path = manager.encrypt(file, password, output)
            success(f"Encrypted to {output_path}")
            info("Store this file safely. You can commit it to git.")
            sys.exit(0)
        except Exception as e:
            error(f"Encryption failed: {e}")
            sys.exit(1)

    # Decrypt
    if decrypt:
        try:
            output_path = manager.decrypt(file, password, output)
            success(f"Decrypted to {output_path}")
            warning("Do NOT commit decrypted .env files to git!")
            sys.exit(0)
        except Exception as e:
            error(f"Decryption failed: {e}")
            sys.exit(1)

    # Validate
    if validate:
        try:
            is_valid, missing = manager.validate(file, list(validate))

            if is_valid:
                success("All required variables are present!")
                sys.exit(0)
            else:
                error(f"Missing required variables: {', '.join(missing)}")
                sys.exit(1)
        except Exception as e:
            error(f"Validation failed: {e}")
            sys.exit(1)

    # Diff
    if diff:
        try:
            differences = manager.diff(file, diff)

            if not differences:
                success("Files are identical")
                sys.exit(0)

            info(f"Found {len(differences)} difference(s)")

            table = create_table(title="Environment Differences")
            table.add_column("Variable", style="cyan")
            table.add_column(file.name, style="yellow")
            table.add_column(diff.name, style="magenta")

            for key, (val1, val2) in differences.items():
                table.add_row(
                    key,
                    val1 or "[red](missing)[/red]",
                    val2 or "[red](missing)[/red]",
                )

            print_table(table)
            sys.exit(0)

        except Exception as e:
            error(f"Diff failed: {e}")
            sys.exit(1)

    # If no action specified
    error("Please specify an action: --encrypt, --decrypt, --validate, or --diff")
    sys.exit(1)


if __name__ == "__main__":
    main()
