"""SQLAlchemy models for the Smart Coffee Shop modular monolith."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    users: Mapped[list[User]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    role: Mapped[Role] = relationship(back_populates="users")
    employee: Mapped[Employee | None] = relationship(back_populates="user")
    auth_sessions: Mapped[list[AuthSession]] = relationship(back_populates="user")
    order_events: Mapped[list[OrderEvent]] = relationship(back_populates="actor")
    inventory_transactions: Mapped[list[InventoryTransaction]] = relationship(
        back_populates="actor"
    )
    loyalty_transactions: Mapped[list[LoyaltyTransaction]] = relationship(
        back_populates="actor"
    )


Index("uq_users_email_lower", func.lower(User.email), unique=True)


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)
    employee_code: Mapped[str] = mapped_column(String(32), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    user: Mapped[User | None] = relationship(back_populates="employee")
    orders: Mapped[list[Order]] = relationship(back_populates="employee")


Index("uq_employees_code_lower", func.lower(Employee.employee_code), unique=True)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    orders: Mapped[list[Order]] = relationship(back_populates="customer")
    loyalty_transactions: Mapped[list[LoyaltyTransaction]] = relationship(
        back_populates="customer"
    )


Index("uq_customers_email_lower", func.lower(Customer.email), unique=True)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    products: Mapped[list[Product]] = relationship(back_populates="category")


Index("uq_categories_name_lower", func.lower(Category.name), unique=True)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("base_price >= 0", name="base_price_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    base_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    category: Mapped[Category] = relationship(back_populates="products")
    variants: Mapped[list[ProductVariant]] = relationship(back_populates="product")
    toppings: Mapped[list[ProductTopping]] = relationship(back_populates="product")


Index(
    "uq_products_category_name_lower",
    Product.category_id,
    func.lower(Product.name),
    unique=True,
)


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("product_id", "name"),
        CheckConstraint("price >= 0", name="price_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    sku: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        server_default=text(
            "'VAR-' || lpad(nextval('product_variant_sku_seq')::text, 6, '0')"
        ),
    )
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    product: Mapped[Product] = relationship(back_populates="variants")
    recipes: Mapped[list[Recipe]] = relationship(back_populates="variant")
    order_items: Mapped[list[OrderItem]] = relationship(back_populates="variant")


class ProductTopping(Base):
    __tablename__ = "product_toppings"
    __table_args__ = (
        UniqueConstraint("product_id", "name"),
        CheckConstraint("price >= 0", name="price_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    product: Mapped[Product] = relationship(back_populates="toppings")


Index("uq_product_variants_sku_lower", func.lower(ProductVariant.sku), unique=True)
Index(
    "uq_product_variants_product_name_lower",
    ProductVariant.product_id,
    func.lower(ProductVariant.name),
    unique=True,
)


class CafeTable(Base):
    __tablename__ = "cafe_tables"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    table_number: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    sessions: Mapped[list[TableSession]] = relationship(back_populates="table")


Index("uq_cafe_tables_number_lower", func.lower(CafeTable.table_number), unique=True)


class TableSession(Base):
    __tablename__ = "table_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'paid', 'cancelled')", name="status_valid"),
        Index(
            "uq_table_sessions_open_table",
            "table_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("cafe_tables.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'open'"))
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    table: Mapped[CafeTable] = relationship(back_populates="sessions")
    orders: Mapped[list[Order]] = relationship(
        back_populates="table_session", order_by="Order.sequence_number"
    )
    payments: Mapped[list[Payment]] = relationship(back_populates="table_session")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("subtotal_amount >= 0", name="subtotal_nonnegative"),
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 20",
            name="discount_percent_valid",
        ),
        CheckConstraint("discount_amount >= 0", name="discount_nonnegative"),
        CheckConstraint("total_amount >= 0", name="total_nonnegative"),
        CheckConstraint(
            "subtotal_amount - discount_amount = total_amount",
            name="total_components_valid",
        ),
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'placed', 'paid', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint(
            "order_type IS NULL OR order_type IN ('initial', 'additional')",
            name="order_type_valid",
        ),
        UniqueConstraint("session_id", "sequence_number"),
        Index(
            "uq_orders_session_additional_draft",
            "session_id",
            unique=True,
            postgresql_where=text("status = 'draft' AND order_type = 'additional'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id"), index=True
    )
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"), index=True
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("table_sessions.id"), index=True
    )
    order_type: Mapped[str | None] = mapped_column(String(20))
    sequence_number: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'"))
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), server_default=text("0")
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default=text("0")
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    customer: Mapped[Customer | None] = relationship(back_populates="orders")
    employee: Mapped[Employee | None] = relationship(back_populates="orders")
    table_session: Mapped[TableSession | None] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", order_by="OrderItem.id"
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="order", order_by="Payment.id"
    )
    events: Mapped[list[OrderEvent]] = relationship(
        back_populates="order", order_by="OrderEvent.id"
    )
    loyalty_transactions: Mapped[list[LoyaltyTransaction]] = relationship(
        back_populates="order", order_by="LoyaltyTransaction.id"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_nonnegative"),
        CheckConstraint("line_total >= 0", name="line_total_nonnegative"),
        CheckConstraint("unit_price * quantity = line_total", name="line_total_valid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id"), index=True
    )
    product_name: Mapped[str] = mapped_column(String(150))
    variant_name: Mapped[str] = mapped_column(String(100))
    sku: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    order: Mapped[Order] = relationship(back_populates="items")
    variant: Mapped[ProductVariant] = relationship(back_populates="order_items")
    inventory_transactions: Mapped[list[InventoryTransaction]] = relationship(
        back_populates="order_item"
    )
    topping_snapshots: Mapped[list[OrderItemTopping]] = relationship(
        back_populates="order_item", order_by="OrderItemTopping.id"
    )


class OrderItemTopping(Base):
    __tablename__ = "order_item_toppings"
    __table_args__ = (CheckConstraint("price >= 0", name="price_nonnegative"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"), index=True)
    topping_id: Mapped[int | None] = mapped_column(ForeignKey("product_toppings.id"))
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    order_item: Mapped[OrderItem] = relationship(back_populates="topping_snapshots")


class OrderEvent(Base):
    __tablename__ = "order_events"
    __table_args__ = (
        CheckConstraint(
            "to_status IN ('draft', 'confirmed', 'placed', 'paid', 'cancelled')",
            name="to_status_valid",
        ),
        CheckConstraint(
            "from_status IS NULL OR "
            "from_status IN ('draft', 'confirmed', 'placed', 'paid', 'cancelled')",
            name="from_status_valid",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    order: Mapped[Order] = relationship(back_populates="events")
    actor: Mapped[User] = relationship(back_populates="order_events")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "cash_received IS NULL OR "
            "(cash_received >= amount AND change_amount = cash_received - amount)",
            name="cash_values_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'refunded')",
            name="status_valid",
        ),
        Index(
            "uq_payments_succeeded_order",
            "order_id",
            unique=True,
            postgresql_where=text("status = 'succeeded'"),
        ),
        Index(
            "uq_payments_succeeded_session",
            "session_id",
            unique=True,
            postgresql_where=text("status = 'succeeded' AND session_id IS NOT NULL"),
        ),
        Index(
            "ix_payments_reporting_status_created_order",
            "status",
            "created_at",
            "order_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("table_sessions.id"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    provider_reference: Mapped[str | None] = mapped_column(String(128), unique=True)
    receipt_number: Mapped[str | None] = mapped_column(String(40), unique=True)
    cashier_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    cash_received: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    change_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    transfer_reference: Mapped[str | None] = mapped_column(String(128))
    method: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    order: Mapped[Order | None] = relationship(back_populates="payments")
    table_session: Mapped[TableSession | None] = relationship(back_populates="payments")


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"
    __table_args__ = (
        CheckConstraint("points_delta <> 0", name="points_delta_nonzero"),
        CheckConstraint(
            "transaction_type IN ('earn', 'refund', 'adjustment')",
            name="type_valid",
        ),
        CheckConstraint(
            "(transaction_type = 'earn' AND points_delta > 0) "
            "OR (transaction_type = 'refund' AND points_delta < 0) "
            "OR transaction_type = 'adjustment'",
            name="points_direction_valid",
        ),
        CheckConstraint(
            "transaction_type = 'adjustment' OR order_id IS NOT NULL",
            name="order_required",
        ),
        CheckConstraint("char_length(btrim(reason)) >= 3", name="reason_valid"),
        Index(
            "uq_loyalty_earn_order",
            "order_id",
            unique=True,
            postgresql_where=text("transaction_type = 'earn'"),
        ),
        Index(
            "uq_loyalty_refund_order",
            "order_id",
            unique=True,
            postgresql_where=text("transaction_type = 'refund'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    transaction_type: Mapped[str] = mapped_column(String(20))
    points_delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    customer: Mapped[Customer] = relationship(back_populates="loyalty_transactions")
    order: Mapped[Order | None] = relationship(back_populates="loyalty_transactions")
    actor: Mapped[User | None] = relationship(back_populates="loyalty_transactions")


class Ingredient(Base):
    __tablename__ = "ingredients"
    __table_args__ = (
        CheckConstraint("unit IN ('g', 'ml', 'piece')", name="unit_valid"),
        CheckConstraint(
            "low_stock_threshold >= 0", name="low_stock_threshold_nonnegative"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    unit: Mapped[str] = mapped_column(String(20))
    low_stock_threshold: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    recipes: Mapped[list[Recipe]] = relationship(back_populates="ingredient")
    transactions: Mapped[list[InventoryTransaction]] = relationship(
        back_populates="ingredient"
    )


Index("uq_ingredients_sku_lower", func.lower(Ingredient.sku), unique=True)
Index("uq_ingredients_name_lower", func.lower(Ingredient.name), unique=True)


class Recipe(Base):
    __tablename__ = "recipes"
    __table_args__ = (
        UniqueConstraint("variant_id", "ingredient_id"),
        CheckConstraint("quantity_required > 0", name="quantity_positive"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), index=True)
    quantity_required: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    variant: Mapped[ProductVariant] = relationship(back_populates="recipes")
    ingredient: Mapped[Ingredient] = relationship(back_populates="recipes")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    __table_args__ = (
        CheckConstraint("quantity_delta <> 0", name="delta_nonzero"),
        CheckConstraint(
            "(transaction_type IN ('sale', 'waste') AND quantity_delta < 0) "
            "OR (transaction_type IN ('purchase', 'return') AND quantity_delta > 0) "
            "OR transaction_type = 'adjustment'",
            name="delta_direction_valid",
        ),
        CheckConstraint(
            "transaction_type IN ('purchase', 'sale', 'return', 'adjustment', 'waste')",
            name="type_valid",
        ),
        CheckConstraint(
            "transaction_type NOT IN ('sale', 'return') OR order_item_id IS NOT NULL",
            name="order_movement_has_order_item",
        ),
        CheckConstraint("char_length(btrim(reason)) >= 3", name="reason_valid"),
        Index(
            "uq_inventory_sale_item_ingredient",
            "order_item_id",
            "ingredient_id",
            unique=True,
            postgresql_where=text("transaction_type = 'sale'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), index=True)
    order_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("order_items.id"), index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True
    )
    reversal_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_transactions.id"), unique=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    transaction_type: Mapped[str] = mapped_column(String(20))
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reason: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ingredient: Mapped[Ingredient] = relationship(back_populates="transactions")
    order_item: Mapped[OrderItem | None] = relationship(
        back_populates="inventory_transactions"
    )
    actor: Mapped[User | None] = relationship(back_populates="inventory_transactions")


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="auth_session_expiry_valid"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="auth_sessions")
