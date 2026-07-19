"""Library — the cross-catalog view of everything the seller has stored.

The per-SKU asset route answers "what does this product have?"; the library answers "what
do I have?" — the organize-and-search half of the storage story, over the same documents.
Filters run server-side so the presign cost (one signed URL per returned asset) is paid
only for the page actually being shown, not for the whole catalog on every keystroke.

`q` matches by content-hash prefix on the asset itself, its parent, or the asset it was
replayed from. Hashes are how everything else in this system names media (the ledger,
/verify, the export certificates), so the library must be searchable by the same handle —
"which of my files is 4b2b705d…?" is a question the ledger page genuinely produces.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, get_current_user
from ..models import AssetOut, Modality, Style
from ..repo import get_repo
from ..util import with_presigned_url

router = APIRouter(tags=["library"])


def _qa_state(asset: dict) -> str:
    """passed | flagged | none — absence of a report is its own state, never a pass."""
    report = asset.get("qa")
    if not report:
        return "none"
    return "passed" if report.get("passed") else "flagged"


@router.get("/assets", response_model=list[AssetOut])
def list_library(
    style: Style | None = None,
    modality: Modality | None = None,
    authentic: bool | None = Query(default=None),
    qa: str | None = Query(default=None, pattern="^(passed|flagged|none)$"),
    q: str | None = Query(default=None, max_length=64, description="content-hash prefix"),
    limit: int = Query(default=120, ge=1, le=500),
    user: CurrentUser = Depends(get_current_user),
):
    assets = get_repo().list_assets_for_user(user.uid)

    if style is not None:
        assets = [a for a in assets if a.get("style") == style.value]
    if modality is not None:
        assets = [a for a in assets if a.get("modality") == modality.value]
    if authentic is not None:
        assets = [a for a in assets if bool(a.get("is_authentic")) == authentic]
    if qa is not None:
        assets = [a for a in assets if _qa_state(a) == qa]
    if q:
        needle = q.strip().lower()
        assets = [
            a for a in assets
            if str(a.get("sha256") or "").startswith(needle)
            or str(a.get("parent_sha256") or "").startswith(needle)
            or str(a.get("replay_of") or "").startswith(needle)
        ]

    return [with_presigned_url(a) for a in assets[:limit]]
