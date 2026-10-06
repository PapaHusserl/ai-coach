"""sync: sync (из Garmin) и import_fit (из FIT)."""

from ai_coach.sync.fit_import import FitImportError, import_fit
from ai_coach.sync.garmin_sync import sync

__all__ = ["FitImportError", "import_fit", "sync"]
