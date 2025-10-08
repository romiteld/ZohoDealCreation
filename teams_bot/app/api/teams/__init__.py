"""
Teams Bot API - Import shim for Phase 1 deployment.

This module re-exports routes from app.api.teams to make them available
to the Teams Bot service container. This is a temporary solution until
Phase 2-3 when these routes will be moved to the well_shared library.

TODO (Phase 2-3): Replace with well_shared.teams.routes import
"""

# Re-export routes from main app directory
# This allows the Teams Bot container to import from app.api.teams.routes
# while the actual implementation stays in the main app/ directory
from app.api.teams.routes import *  # noqa: F401, F403
from app.api.teams.adaptive_cards import *  # noqa: F401, F403
from app.api.teams.query_engine import *  # noqa: F401, F403
