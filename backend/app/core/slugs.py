"""Helpers for generating and validating unique public storefront slugs."""

import re
import unicodedata
from typing import Optional

from sqlalchemy.orm import Session

RESERVED_SHOP_SLUGS = frozenset({
    "admin",
    "api",
    "store",
    "stores",
    "catalogue",
    "try-on",
    "tryon",
    "shop-dashboard",
    "about",
    "auth",
    "login",
    "register",
    "shops",
    "products",
    "health",
    "uploads",
})

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_SLUG_FORMAT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify_shop_name(name: Optional[str]) -> str:
    """Convert a shop name into a URL-safe lowercase hyphenated slug."""
    raw = unicodedata.normalize("NFKD", (name or "").strip())
    ascii_text = raw.encode("ascii", "ignore").decode("ascii").lower()
    slug = _NON_ALNUM_RE.sub("-", ascii_text).strip("-")
    if not slug:
        slug = "shop"
    slug = slug[:100].strip("-") or "shop"
    if slug in RESERVED_SHOP_SLUGS:
        slug = f"{slug}-shop"[:108].strip("-")
    return slug


def normalize_explicit_slug(raw_slug: str) -> str:
    """Validate and normalize an explicitly requested storefront slug."""
    cleaned = slugify_shop_name(raw_slug)
    if not _SLUG_FORMAT_RE.match(cleaned) or cleaned in RESERVED_SHOP_SLUGS:
        raise ValueError("Storefront slug must contain lowercase letters, numbers, or hyphens and cannot use reserved words.")
    return cleaned


def generate_unique_shop_slug(
    db: Session,
    shop_name: Optional[str],
    exclude_shop_id: Optional[int] = None,
) -> str:
    """Return a unique slug for a shop, appending -2, -3, ... on collisions."""
    from app.models import Shop

    base_slug = slugify_shop_name(shop_name)
    candidate = base_slug
    counter = 2

    while True:
        query = db.query(Shop.id).filter(Shop.slug == candidate)
        if exclude_shop_id is not None:
            query = query.filter(Shop.id != exclude_shop_id)
        if query.first() is None:
            return candidate
        suffix = f"-{counter}"
        candidate = f"{base_slug[:120 - len(suffix)].rstrip('-')}{suffix}"
        if candidate in RESERVED_SHOP_SLUGS:
            candidate = f"{candidate}-shop"
        counter += 1

