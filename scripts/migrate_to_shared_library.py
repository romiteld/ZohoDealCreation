#!/usr/bin/env python3
"""
Automated migration script for Well Shared Library extraction.

This script:
1. Creates the well_shared package structure
2. Moves files to appropriate locations
3. Updates all imports across the codebase
4. Validates the migration
5. Runs tests to ensure nothing broke

Usage:
    python scripts/migrate_to_shared_library.py --dry-run  # Preview changes
    python scripts/migrate_to_shared_library.py --execute  # Apply changes
    python scripts/migrate_to_shared_library.py --validate # Check imports only
"""

import os
import re
import sys
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import subprocess

# Migration mapping: old_path -> new_path
FILE_MIGRATIONS = {
    "app/database_connection_manager.py": "well_shared/well_shared/database/connection.py",
    "app/redis_cache_manager.py": "well_shared/well_shared/cache/redis_manager.py",
    "app/cache/c3.py": "well_shared/well_shared/cache/c3.py",
    "app/cache/voit.py": "well_shared/well_shared/cache/voit.py",
    "app/config/voit_config.py": "well_shared/well_shared/config/voit_config.py",
    "app/extract/evidence.py": "well_shared/well_shared/evidence/extractor.py",
    "app/mail/send.py": "well_shared/well_shared/mail/sender.py",
}

# Import replacements: old_import -> new_import
IMPORT_REPLACEMENTS = {
    r"from app\.database_connection_manager import": "from well_shared.database.connection import",
    r"from well_shared.database import connection as database_connection_manager": "from well_shared.database import connection as database_connection_manager",
    r"from app\.redis_cache_manager import": "from well_shared.cache.redis_manager import",
    r"from well_shared.cache import redis_manager": "from well_shared.cache import redis_manager",
    r"from app\.cache\.c3 import": "from well_shared.cache.c3 import",
    r"from app\.cache\.voit import": "from well_shared.cache.voit import",
    r"from app\.config\.voit_config import": "from well_shared.config.voit_config import",
    r"from app\.extract\.evidence import": "from well_shared.evidence.extractor import",
    r"from app\.mail\.send import": "from well_shared.mail.sender import",
    # Zoho imports: DISABLED - Migration deferred to Phase 3
    # Reason: app/integrations.py contains ZohoClient/ZohoApiClient classes (lines 820-1600+)
    # that are tightly coupled with PostgreSQL, retry decorators, and other utilities.
    # These will be migrated during Phase 3 (Main API refactoring) after Teams Bot
    # and Vault Agent are separated.
    # DO NOT ENABLE until well_shared/zoho/client.py is created and validated.
    # r"from app\.integrations import (get_zoho_headers|...)": "from well_shared.zoho.client import \\1",
}

# CRITICAL FINDING: app/integrations.py uses ZohoClient/ZohoApiClient CLASSES, not functions
# The entire file must remain in app/integrations.py for now
# Zoho migration is DEFERRED until Phase 3 (after Teams/Vault separation)
ZOHO_MIGRATION_DEFERRED = True
ZOHO_DEFERRAL_REASON = """
app/integrations.py contains ZohoClient and ZohoApiClient classes (lines 820-1600+)
that are tightly coupled with:
- PostgreSQL client (line 823)
- Retry decorators (line 845)
- Multiple other utilities

Extracting only Zoho methods would require:
1. Moving entire ZohoClient + ZohoApiClient classes
2. Moving all dependencies (PostgreSQLClient, retry decorators, etc.)
3. This would essentially move most of app/integrations.py

DECISION: Keep app/integrations.py intact for Phase 0-2
Zoho migration happens in Phase 3 when refactoring main API
"""


class MigrationManager:
    def __init__(self, repo_root: Path, dry_run: bool = True):
        self.repo_root = repo_root
        self.dry_run = dry_run
        self.changes_log: List[str] = []

    def log(self, message: str, level: str = "INFO"):
        prefix = "[DRY-RUN] " if self.dry_run else ""
        print(f"{prefix}[{level}] {message}")
        self.changes_log.append(message)

    def create_directory_structure(self):
        """Create the well_shared package directory structure."""
        self.log("Creating well_shared package structure...")

        directories = [
            "well_shared",
            "well_shared/well_shared",
            "well_shared/well_shared/database",
            "well_shared/well_shared/cache",
            "well_shared/well_shared/zoho",
            "well_shared/well_shared/evidence",
            "well_shared/well_shared/mail",
            "well_shared/well_shared/config",
            "well_shared/tests",
        ]

        for directory in directories:
            dir_path = self.repo_root / directory
            if not self.dry_run:
                dir_path.mkdir(parents=True, exist_ok=True)
                (dir_path / "__init__.py").touch(exist_ok=True)
            self.log(f"  Created {directory}")

    def create_setup_py(self):
        """Create setup.py for the well_shared package."""
        setup_content = '''"""
Well Shared Library - Common utilities for Well Intake API ecosystem.

Shared across:
- Well Intake API (main email processing)
- Teams Bot (Microsoft Teams integration)
- Vault Agent (weekly digest generation)
"""

from setuptools import setup, find_packages

setup(
    name="well_shared",
    version="0.1.0",
    description="Shared utilities for Well Intake API services",
    author="The Well Team",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "asyncpg>=0.29.0",
        "redis>=5.0.0",
        "azure-communication-email>=1.0.0",
        "azure-identity>=1.15.0",
        "azure-keyvault-secrets>=4.7.0",
        "openai>=1.12.0",
        "pydantic>=2.5.0",
        "httpx>=0.26.0",
    ],
)
'''
        setup_path = self.repo_root / "well_shared" / "setup.py"
        if not self.dry_run:
            setup_path.write_text(setup_content)
        self.log(f"Created {setup_path}")

    def move_file(self, old_path: str, new_path: str):
        """Move a file from old location to new location."""
        old_file = self.repo_root / old_path
        new_file = self.repo_root / new_path

        if not old_file.exists():
            self.log(f"  ⚠️  Source file not found: {old_path}", "WARN")
            return False

        if not self.dry_run:
            new_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_file), str(new_file))
            self.log(f"  Moved {old_path} -> {new_path}")
        else:
            self.log(f"  Would move {old_path} -> {new_path} (and DELETE source)")

        return True

    def check_zoho_migration_needed(self) -> bool:
        """
        Check if Zoho migration is needed for this phase.

        Returns:
            bool: True if Zoho migration is deferred (safe to proceed), False if blocked
        """
        if ZOHO_MIGRATION_DEFERRED:
            self.log("Zoho migration DEFERRED to Phase 3", "INFO")
            self.log("")
            self.log("Reason:")
            for line in ZOHO_DEFERRAL_REASON.strip().split("\n"):
                self.log(f"  {line}")
            self.log("")
            self.log("Impact:")
            self.log("  - app/integrations.py remains unchanged")
            self.log("  - Teams Bot and Vault Agent will import from app/integrations.py")
            self.log("  - This is SAFE - no breaking changes")
            self.log("")
            return True  # Safe to proceed

        # If not deferred, would need actual extraction logic here
        return False

    def update_imports_in_file(self, file_path: Path) -> int:
        """Update imports in a single file. Returns number of changes."""
        if not file_path.exists() or not file_path.is_file():
            return 0

        if file_path.suffix not in [".py"]:
            return 0

        content = file_path.read_text()
        original_content = content
        changes = 0

        for old_pattern, new_import in IMPORT_REPLACEMENTS.items():
            matches = re.findall(old_pattern, content)
            if matches:
                content = re.sub(old_pattern, new_import, content)
                changes += len(matches)

        if content != original_content:
            if not self.dry_run:
                file_path.write_text(content)
            self.log(f"  Updated {changes} imports in {file_path.relative_to(self.repo_root)}")
            return changes

        return 0

    def update_all_imports(self):
        """Scan all Python files and update imports."""
        self.log("Updating imports across codebase...")

        total_changes = 0
        python_files = list(self.repo_root.rglob("*.py"))

        # Exclude well_shared itself and virtual environments
        python_files = [
            f for f in python_files
            if "well_shared" not in str(f) and "zoho/bin" not in str(f)
        ]

        for py_file in python_files:
            changes = self.update_imports_in_file(py_file)
            total_changes += changes

        self.log(f"Updated {total_changes} total imports across {len(python_files)} files")

    def validate_imports(self) -> bool:
        """Validate that all imports are correct."""
        self.log("Validating imports...")

        if self.dry_run:
            self.log("  [SKIPPED] Import validation not run in dry-run mode")
            self.log("  Run with --execute to perform actual validation")
            return True

        # Try importing the shared library
        try:
            import sys
            python_exe = sys.executable  # Use current interpreter (venv-aware)

            subprocess.run(
                [python_exe, "-c", "import well_shared"],
                check=True,
                cwd=self.repo_root,
                capture_output=True
            )
            self.log("  ✓ well_shared package imports successfully")

            # Validate critical modules can be imported
            critical_modules = [
                "well_shared.database.connection",
                "well_shared.cache.redis_manager",
                "well_shared.cache.c3",
                "well_shared.cache.voit",
                "well_shared.mail.sender",
            ]

            for module in critical_modules:
                try:
                    result = subprocess.run(
                        [python_exe, "-c", f"import {module}"],
                        check=True,
                        cwd=self.repo_root,
                        capture_output=True,
                        text=True
                    )
                    self.log(f"  ✓ {module} imports successfully")
                except subprocess.CalledProcessError as e:
                    self.log(f"  ✗ {module} import failed", "ERROR")
                    if e.stderr:
                        self.log(f"    Error: {e.stderr.strip()}", "ERROR")
                    return False

            return True
        except subprocess.CalledProcessError as e:
            self.log(f"  ✗ Import validation failed: {e}", "ERROR")
            return False

    def run_tests(self) -> bool:
        """Run pytest to ensure migration didn't break anything."""
        self.log("Running tests to validate migration...")

        if self.dry_run:
            self.log("  Skipping tests in dry-run mode")
            return True

        try:
            result = subprocess.run(
                ["pytest", "tests/", "-v", "--tb=short"],
                cwd=self.repo_root,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.log("  ✓ All tests passed")
                return True
            else:
                self.log(f"  ✗ Tests failed:\n{result.stdout}\n{result.stderr}", "ERROR")
                return False
        except Exception as e:
            self.log(f"  ✗ Test execution error: {e}", "ERROR")
            return False

    def execute_migration(self):
        """Execute the full migration process."""
        self.log("=" * 60)
        self.log("Starting Well Shared Library Migration")
        self.log("=" * 60)

        # Phase 1: Create structure
        self.create_directory_structure()
        self.create_setup_py()

        # Phase 2: Check if Zoho migration is deferred (it is for Phase 0)
        self.log("\nChecking Zoho migration status...")
        safe_to_proceed = self.check_zoho_migration_needed()

        if not safe_to_proceed:
            self.log("\n" + "=" * 60, "ERROR")
            self.log("MIGRATION BLOCKED: Zoho migration check failed!", "ERROR")
            self.log("=" * 60, "ERROR")
            return

        # Phase 3: Move files (safe because Zoho migration is deferred)
        self.log("\nMoving files to well_shared...")
        for old_path, new_path in FILE_MIGRATIONS.items():
            self.move_file(old_path, new_path)

        # Phase 4: Update imports
        self.log("\nUpdating imports...")
        self.update_all_imports()

        # Phase 5: Install package
        if not self.dry_run:
            self.log("\nInstalling well_shared package...")
            subprocess.run(
                ["pip", "install", "-e", "./well_shared"],
                cwd=self.repo_root,
                check=True
            )

        # Phase 6: Validate
        self.log("\nValidating migration...")
        imports_valid = self.validate_imports()

        if not self.dry_run and imports_valid:
            tests_passed = self.run_tests()
            if not tests_passed:
                self.log("\n⚠️  Migration completed but tests failed!", "WARN")
                self.log("Review test output and fix any issues before deploying.", "WARN")

        # Summary
        self.log("\n" + "=" * 60)
        if self.dry_run:
            self.log("DRY RUN COMPLETE - No changes made")
            self.log("Review the output above, then run with --execute to apply changes")
        else:
            self.log("MIGRATION COMPLETE")
            self.log(f"Total changes logged: {len(self.changes_log)}")
        self.log("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate shared code to well_shared library"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the migration"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Only validate imports, don't migrate"
    )

    args = parser.parse_args()

    # Default to dry-run if no mode specified
    if not any([args.dry_run, args.execute, args.validate]):
        args.dry_run = True

    repo_root = Path(__file__).parent.parent
    # Validation and execution both need dry_run=False to actually run checks
    manager = MigrationManager(repo_root, dry_run=not (args.execute or args.validate))

    if args.validate:
        manager.validate_imports()
    else:
        manager.execute_migration()


if __name__ == "__main__":
    main()
