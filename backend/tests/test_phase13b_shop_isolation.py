"""
VirtualFit AI — Phase 13B Test Suite: Complete Multi-Shop Product Isolation.

Uses an in-process ASGI caller against the real FastAPI `app` (exercising
route precedence, dependency injection, query/form parsing, and auth headers)
without needing external HTTP test dependencies.

Verifies:
1. Slug generation: unique, URL-safe, collision handling (-2, -3), reserved-word protection.
2. Newly registered shop starts with an empty catalogue (0 products).
3. Creating products derives shop_id server-side from authenticated shop_owner
   and rejects cross-shop shop_id mismatch (403).
4. GET /api/products/my returns ONLY the authenticated shop's inventory (including drafts).
5. Unscoped public GET /api/products is blocked (400), never merging shops globally.
6. Public GET /api/products?is_available=false never exposes unpublished drafts.
7. Shop B owner querying /api/products?shop_id=<ShopA> gets 403.
8. Storefront slug endpoints (/api/shops/slug/{slug}, /products, /products/{id}) isolate
   each shop's published items and return 403 for cross-shop product IDs.
9. PUT /api/products/{id} cannot transfer product.shop_id to another shop (403).
10. Cross-shop edit / delete returns 403.
11. POST /api/tryon rejects cross-shop garment IDs (403), unpublished garments (400),
    and unscoped cross-shop owner requests (403), while accepting matching storefront pairs (202).
"""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
from app.database import SessionLocal
from app.models import Shop, User, Product, TryOnSession
from app.core.slugs import slugify_shop_name, generate_unique_shop_slug
from app.routers.auth import register_limiter
from app.services.tryon.storage import delete_customer_photo, delete_result_file

VALID_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xc0\x00\x11\x08\x03\x60\x02\x40\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
    + (b"\xaa" * 500)
)


class SimpleResponse:
    def __init__(self, status_code: int, body: bytes):
        self.status_code = status_code
        self.body = body

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


def _encode_multipart(
    fields: Dict[str, str],
    files: Dict[str, Tuple[str, bytes, str]],
) -> Tuple[bytes, str]:
    boundary = f"----VirtualFitTest{uuid.uuid4().hex}"
    chunks: List[bytes] = []
    for k, v in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
        chunks.append(f"{v}\r\n".encode("utf-8"))
    for k, (fname, data, ctype) in files.items():
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(
            f'Content-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'.encode("utf-8")
        )
        chunks.append(f"Content-Type: {ctype}\r\n\r\n".encode("ascii"))
        chunks.append(data)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


async def _asgi_call(
    method: str,
    target: str,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    form_fields: Optional[Dict[str, str]] = None,
    files: Optional[Dict[str, Tuple[str, bytes, str]]] = None,
) -> SimpleResponse:
    parsed = urlsplit(target)
    body = b""
    req_headers: List[Tuple[bytes, bytes]] = [
        (b"host", b"testserver"),
    ]
    if headers:
        for k, v in headers.items():
            req_headers.append((k.lower().encode("ascii"), v.encode("utf-8")))

    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        req_headers.append((b"content-type", b"application/json"))
    elif form_fields is not None or files is not None:
        body, content_type = _encode_multipart(form_fields or {}, files or {})
        req_headers.append((b"content-type", content_type.encode("ascii")))

    req_headers.append((b"content-length", str(len(body)).encode("ascii")))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": parsed.path,
        "raw_path": parsed.path.encode("ascii"),
        "query_string": parsed.query.encode("ascii"),
        "headers": req_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }

    sent_body = False

    async def receive():
        nonlocal sent_body
        if not sent_body:
            sent_body = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    status_code = 500
    response_chunks: List[bytes] = []

    async def send(message):
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            chunk = message.get("body", b"")
            if chunk:
                response_chunks.append(chunk)

    await app(scope, receive, send)
    return SimpleResponse(status_code=status_code, body=b"".join(response_chunks))


def api_call(method: str, target: str, **kwargs) -> SimpleResponse:
    return asyncio.run(_asgi_call(method, target, **kwargs))


def test_slug_helpers():
    print("\n--- Test 1: Slug Normalization, Reserved Words, and Collision Suffixes ---")
    assert slugify_shop_name("Urban Threads & Co.") == "urban-threads-co"
    assert slugify_shop_name("admin") == "admin-shop"
    assert slugify_shop_name("store") == "store-shop"
    assert slugify_shop_name("try-on") == "try-on-shop"
    assert slugify_shop_name("   !!!   ") == "shop"

    db = SessionLocal()
    uid = uuid.uuid4().hex[:6]
    base_name = f"Atelier Silk {uid}"
    s1 = Shop(shop_name=base_name, slug=generate_unique_shop_slug(db, base_name))
    db.add(s1)
    db.commit()
    db.refresh(s1)
    try:
        second_slug = generate_unique_shop_slug(db, base_name)
        assert second_slug == f"{s1.slug}-2", f"Expected collision suffix -2, got {second_slug}"
        print(f"  ✓ Slug helpers verified ({s1.slug} -> {second_slug})")
    finally:
        db.delete(s1)
        db.commit()
        db.close()


def test_end_to_end_multi_shop_isolation():
    print("\n--- Test 2: Full Multi-Shop HTTP Isolation & Storefront Contracts ---")
    uid = uuid.uuid4().hex[:8]
    orig_provider = os.environ.get("TRYON_PROVIDER")
    os.environ["TRYON_PROVIDER"] = "mock"

    for attr in ("_requests", "_hits", "_buckets"):
        store = getattr(register_limiter, attr, None)
        if isinstance(store, dict):
            store.clear()

    created_shop_ids: List[int] = []
    created_user_ids: List[int] = []
    created_session_ids: List[str] = []

    try:
        # 1. Register Shop A owner
        res_a = api_call(
            "POST",
            "/api/auth/register",
            json_body={
                "email": f"shop_a_{uid}@example.com",
                "password": "ShopPassword123!",
                "full_name": "Owner Alpha",
                "role": "shop_owner",
                "shop_name": f"Alpha Couture {uid}",
            },
        )
        assert res_a.status_code == 201, res_a.text
        data_a = res_a.json()
        token_a = data_a["access_token"]
        user_a = data_a["user"]
        shop_a_id = user_a["shop_id"]
        shop_a_slug = user_a["shop_slug"]
        assert shop_a_id is not None and shop_a_slug
        created_shop_ids.append(shop_a_id)
        created_user_ids.append(user_a["id"])
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 2. Register Shop B owner & Customer C
        res_b = api_call(
            "POST",
            "/api/auth/register",
            json_body={
                "email": f"shop_b_{uid}@example.com",
                "password": "ShopPassword123!",
                "full_name": "Owner Beta",
                "role": "shop_owner",
                "shop_name": f"Beta Studio {uid}",
            },
        )
        assert res_b.status_code == 201, res_b.text
        data_b = res_b.json()
        token_b = data_b["access_token"]
        user_b = data_b["user"]
        shop_b_id = user_b["shop_id"]
        shop_b_slug = user_b["shop_slug"]
        assert shop_b_id != shop_a_id and shop_b_slug != shop_a_slug
        created_shop_ids.append(shop_b_id)
        created_user_ids.append(user_b["id"])
        headers_b = {"Authorization": f"Bearer {token_b}"}

        res_c = api_call(
            "POST",
            "/api/auth/register",
            json_body={
                "email": f"cust_c_{uid}@example.com",
                "password": "CustPassword123!",
                "full_name": "Customer Gamma",
                "role": "customer",
            },
        )
        assert res_c.status_code == 201, res_c.text
        token_c = res_c.json()["access_token"]
        created_user_ids.append(res_c.json()["user"]["id"])
        headers_c = {"Authorization": f"Bearer {token_c}"}

        # 3. Newly registered Shop B must start empty (0 products)
        b_my_initial = api_call("GET", "/api/products/my", headers=headers_b)
        assert b_my_initial.status_code == 200, b_my_initial.text
        assert b_my_initial.json() == []

        b_pub_initial = api_call("GET", f"/api/shops/slug/{shop_b_slug}/products")
        assert b_pub_initial.status_code == 200, b_pub_initial.text
        assert b_pub_initial.json() == []

        # 4. Shop A creates 1 published product + 1 unpublished draft (omitting shop_id -> server derived)
        a_prod_1 = api_call(
            "POST",
            "/api/products",
            headers=headers_a,
            json_body={
                "product_name": f"Alpha Silk Top {uid}",
                "category": "Tops",
                "price": 1999,
                "size": "M",
                "color": "Ivory",
                "image_url": "/uploads/garments/sample.jpg",
                "is_available": True,
            },
        )
        assert a_prod_1.status_code == 201, a_prod_1.text
        a1 = a_prod_1.json()
        assert a1["shop_id"] == shop_a_id

        a_prod_draft = api_call(
            "POST",
            "/api/products",
            headers=headers_a,
            json_body={
                "product_name": f"Alpha Hidden Draft {uid}",
                "category": "Tops",
                "price": 2500,
                "image_url": "/uploads/garments/sample.jpg",
                "is_available": False,
            },
        )
        assert a_prod_draft.status_code == 201, a_prod_draft.text
        a_draft = a_prod_draft.json()
        assert a_draft["shop_id"] == shop_a_id
        assert a_draft["is_available"] is False

        # Spoofed shop_id in create payload MUST return 403
        spoof_create = api_call(
            "POST",
            "/api/products",
            headers=headers_b,
            json_body={
                "shop_id": shop_a_id,
                "product_name": "Spoofed Garment",
                "category": "Tops",
                "price": 100,
                "is_available": True,
            },
        )
        assert spoof_create.status_code == 403

        # 5. Global unscoped GET /api/products rejected (400) for anon & customer
        assert api_call("GET", "/api/products").status_code == 400
        assert api_call("GET", "/api/products", headers=headers_c).status_code == 400

        # 6. Shop B owner querying Shop A via /api/products?shop_id=... rejected (403)
        assert api_call("GET", f"/api/products?shop_id={shop_a_id}", headers=headers_b).status_code == 403
        assert api_call("GET", f"/api/products/{a1['id']}", headers=headers_b).status_code == 403

        # 7. Public customer sees ONLY Shop A's published item, NEVER drafts even with is_available=false
        a_pub_list = api_call(
            "GET",
            f"/api/products?shop_slug={shop_a_slug}&is_available=false",
            headers=headers_c,
        )
        assert a_pub_list.status_code == 200, a_pub_list.text
        ids_returned = [p["id"] for p in a_pub_list.json()]
        assert a1["id"] in ids_returned
        assert a_draft["id"] not in ids_returned, "Unpublished drafts must never leak to public callers"

        # Storefront slug product endpoints
        sf_a = api_call("GET", f"/api/shops/slug/{shop_a_slug}")
        assert sf_a.status_code == 200, sf_a.text
        assert sf_a.json()["product_count"] == 1
        assert api_call("GET", f"/api/shops/slug/{shop_b_slug}/products/{a1['id']}").status_code == 403
        assert api_call("GET", f"/api/shops/slug/{shop_a_slug}/products/{a_draft['id']}").status_code == 404

        # 8. Shop B creates its own garment & verifies Shop A and Shop B inventories stay separate
        b_prod = api_call(
            "POST",
            "/api/products",
            headers=headers_b,
            json_body={
                "product_name": f"Beta Denim Jacket {uid}",
                "category": "Outerwear",
                "price": 4500,
                "image_url": "/uploads/garments/sample.jpg",
                "is_available": True,
            },
        )
        assert b_prod.status_code == 201, b_prod.text
        b1 = b_prod.json()
        assert b1["shop_id"] == shop_b_id

        assert [p["id"] for p in api_call("GET", "/api/products/my", headers=headers_b).json()] == [b1["id"]]
        assert set(p["id"] for p in api_call("GET", "/api/products/my", headers=headers_a).json()) == {a1["id"], a_draft["id"]}

        # 9. Prohibit transferring product.shop_id, cross-shop update, cross-shop delete
        assert api_call("PUT", f"/api/products/{a1['id']}", headers=headers_a, json_body={"shop_id": shop_b_id}).status_code == 403
        assert api_call("PUT", f"/api/products/{a1['id']}", headers=headers_b, json_body={"price": 1}).status_code == 403
        assert api_call("DELETE", f"/api/products/{a1['id']}", headers=headers_b).status_code == 403

        # 10. Virtual Try-On shop isolation checks
        # 10a. Trying Shop A's garment while inside Shop B's storefront slug -> 403
        bad_tryon = api_call(
            "POST",
            "/api/tryon",
            headers=headers_c,
            files={"customer_photo": ("person.jpg", VALID_JPEG_BYTES, "image/jpeg")},
            form_fields={"product_id": str(a1["id"]), "shop_slug": shop_b_slug},
        )
        assert bad_tryon.status_code == 403, bad_tryon.text

        # 10b. Shop B owner calling /api/tryon unscoped with Shop A's garment -> 403
        owner_bad_tryon = api_call(
            "POST",
            "/api/tryon",
            headers=headers_b,
            files={"customer_photo": ("person.jpg", VALID_JPEG_BYTES, "image/jpeg")},
            form_fields={"product_id": str(a1["id"])},
        )
        assert owner_bad_tryon.status_code == 403, owner_bad_tryon.text

        # 10c. Trying unpublished draft garment -> 400
        draft_tryon = api_call(
            "POST",
            "/api/tryon",
            headers=headers_c,
            files={"customer_photo": ("person.jpg", VALID_JPEG_BYTES, "image/jpeg")},
            form_fields={"product_id": str(a_draft["id"]), "shop_slug": shop_a_slug},
        )
        assert draft_tryon.status_code == 400, draft_tryon.text

        # 10d. Valid try-on matching Shop A storefront slug -> 202
        ok_tryon = api_call(
            "POST",
            "/api/tryon",
            headers=headers_c,
            files={"customer_photo": ("person.jpg", VALID_JPEG_BYTES, "image/jpeg")},
            form_fields={"product_id": str(a1["id"]), "shop_slug": shop_a_slug},
        )
        assert ok_tryon.status_code == 202, ok_tryon.text
        tryon_json = ok_tryon.json()
        assert tryon_json["shop_id"] == shop_a_id
        assert tryon_json["shop_slug"] == shop_a_slug
        created_session_ids.append(tryon_json["session_id"])

        print("  ✓ All Phase 13B multi-shop isolation and storefront contracts passed!")
    finally:
        if orig_provider is None:
            os.environ.pop("TRYON_PROVIDER", None)
        else:
            os.environ["TRYON_PROVIDER"] = orig_provider

        db = SessionLocal()
        try:
            for sid in created_session_ids:
                s = db.get(TryOnSession, sid)
                if s:
                    if s.customer_photo_url:
                        delete_customer_photo(Path(s.customer_photo_url).name)
                    if s.result_image_url:
                        delete_result_file(Path(s.result_image_url).name)
                    db.delete(s)
            for uid_pk in created_user_ids:
                u = db.get(User, uid_pk)
                if u:
                    db.delete(u)
            db.flush()
            for sh_id in created_shop_ids:
                sh = db.get(Shop, sh_id)
                if sh:
                    db.delete(sh)
            db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    test_slug_helpers()
    test_end_to_end_multi_shop_isolation()
    print("\nALL PHASE 13B SHOP ISOLATION TESTS PASSED!")
