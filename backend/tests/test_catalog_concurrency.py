"""PostgreSQL concurrency checks for category reassignment."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalog.repository import CatalogRepository
from app.catalog.schemas import CategoryReassignDelete, VariantCreate
from app.catalog.service import CatalogService
from app.db.models import Category, Product, ProductVariant
from app.db.session import create_db_engine


def test_concurrent_product_assignment_cannot_orphan_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a migrated PostgreSQL test DB")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end with _test")

    suffix = uuid4().hex
    engine = create_db_engine(url)
    ids: dict[str, int] = {}
    source_locked = Event()
    concurrent_insert_started = Event()
    original_reassign = CatalogRepository.reassign_products

    def coordinated_reassign(
        repository: CatalogRepository,
        source_category_id: int,
        replacement_category_id: int,
    ) -> int:
        source_locked.set()
        assert concurrent_insert_started.wait(timeout=10)
        return original_reassign(
            repository, source_category_id, replacement_category_id
        )

    monkeypatch.setattr(CatalogRepository, "reassign_products", coordinated_reassign)
    try:
        with Session(engine) as db, db.begin():
            source = Category(name=f"Source {suffix}")
            replacement = Category(name=f"Replacement {suffix}")
            db.add_all([source, replacement])
            db.flush()
            product = Product(category_id=source.id, name=f"Existing {suffix}")
            db.add(product)
            db.flush()
            ids.update(
                source=source.id,
                replacement=replacement.id,
                product=product.id,
            )

        def reassign() -> str:
            with Session(engine, expire_on_commit=False) as db:
                CatalogService(db).reassign_and_delete_category(
                    ids["source"],
                    CategoryReassignDelete(replacement_category_id=ids["replacement"]),
                )
            return "reassigned"

        def assign_concurrently() -> str:
            assert source_locked.wait(timeout=10)
            with Session(engine) as db:
                try:
                    with db.begin():
                        db.add(
                            Product(
                                category_id=ids["source"],
                                name=f"Concurrent {suffix}",
                            )
                        )
                        concurrent_insert_started.set()
                        db.flush()
                except IntegrityError:
                    return "rejected"
            return "inserted"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda fn: fn(), (reassign, assign_concurrently)))

        assert sorted(results) == ["reassigned", "rejected"]
        with Session(engine) as db:
            assert db.get(Category, ids["source"]) is None
            saved_product = db.get(Product, ids["product"])
            assert saved_product is not None
            assert saved_product.category_id == ids["replacement"]
            assert (
                db.scalar(
                    select(func.count(Product.id)).where(
                        Product.category_id == ids["source"]
                    )
                )
                == 0
            )
    finally:
        if ids:
            with Session(engine) as db, db.begin():
                db.execute(
                    delete(Product).where(
                        Product.category_id.in_(
                            [ids.get("source"), ids.get("replacement")]
                        )
                    )
                )
                db.execute(
                    delete(Category).where(
                        Category.id.in_([ids.get("source"), ids.get("replacement")])
                    )
                )
        engine.dispose()


def test_concurrent_variant_creation_uses_unique_generated_skus() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a migrated PostgreSQL test DB")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end with _test")

    suffix = uuid4().hex
    engine = create_db_engine(url)
    ids: dict[str, int] = {}
    barrier = Event()
    ready = Event()
    try:
        with Session(engine) as db, db.begin():
            category = Category(name=f"SKU category {suffix}")
            db.add(category)
            db.flush()
            product = Product(category_id=category.id, name=f"SKU product {suffix}")
            db.add(product)
            db.flush()
            ids.update(category=category.id, product=product.id)

        def create_size(name: str) -> str:
            if name == "M":
                ready.set()
            else:
                assert ready.wait(timeout=10)
                barrier.set()
            assert barrier.wait(timeout=10)
            with Session(engine, expire_on_commit=False) as db:
                variant = CatalogService(db).create_variant(
                    ids["product"],
                    VariantCreate(name=name, price="5000.00"),
                )
                return variant.sku

        with ThreadPoolExecutor(max_workers=2) as pool:
            skus = list(pool.map(create_size, ("M", "L")))

        assert len(set(skus)) == 2
        assert all(sku.startswith("VAR-") and sku[4:].isdigit() for sku in skus)
        with Session(engine) as db:
            persisted = set(
                db.scalars(
                    select(ProductVariant.sku).where(
                        ProductVariant.product_id == ids["product"]
                    )
                ).all()
            )
            assert persisted == set(skus)
    finally:
        if ids:
            with Session(engine) as db, db.begin():
                db.execute(
                    delete(ProductVariant).where(
                        ProductVariant.product_id == ids["product"]
                    )
                )
                db.execute(delete(Product).where(Product.id == ids["product"]))
                db.execute(delete(Category).where(Category.id == ids["category"]))
        engine.dispose()
