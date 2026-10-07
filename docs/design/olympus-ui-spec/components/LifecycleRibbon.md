# LifecycleRibbon

Journey-specific lifecycle stages in order; each stage shows its lane code so time maps to place.

- **Provide:** `journey`, `stage` (index being viewed), optional `onStage`, optional `compact`.
- Done ✓ `success`, current ● `active` with outline, future ○ `text-secondary`. When viewing a snapshot, the live stage carries a LIVE tag.
- Production: clicking a past stage opens recorded history; future stages are not viewable.
