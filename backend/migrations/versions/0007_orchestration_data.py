"""Company data for the orchestration agents (substitutes, supplier offers, order history)
and the orchestration result of an inquiry.

Revision ID: 0007_orchestration_data
Revises: 0006_company_data_and_checks
Create Date: 2026-11-11

"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_orchestration_data"
down_revision: str | Sequence[str] | None = "0006_company_data_and_checks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Substitutes of seed products. The S-03 seed inquiries do not ask for them, so their
# check results stay as they were.
SEED_PRODUCTS = [
    {
        "code": "ABC-110",
        "name": "Czujnik ciśnienia ABC-110",
        "list_price": Decimal("125.00"),
        "stock_quantity": 40,
    },
    {
        "code": "XYZ-310",
        "name": "Zawór proporcjonalny XYZ-310",
        "list_price": Decimal("250.00"),
        "stock_quantity": 100,
    },
]

# (product code, substitute code, compatibility, note)
SEED_SUBSTITUTES = [
    ("ABC-100", "ABC-110", "full", "Ten sam zakres pomiarowy i przyłącze."),
    ("XYZ-300", "XYZ-310", "partial", "Inne złącze sterujące, wymaga adaptera."),
]

# (product code, supplier, quantity, lead time in days from the inquiry's reference date).
# ACME: 2026-11-02 + 7 = 2026-11-09, after its Friday 2026-11-06; Delta gets 200 of 450.
# Omega: 2026-11-05 + 5 = 2026-11-10, before 2026-11-12, and covers the 60 missing.
SEED_SUPPLIER_OFFERS = [
    ("ABC-100", "Sensortech Polska", 200, 7),
    ("XYZ-300", "Hydro-Valve", 80, 5),
]

# (customer name, product code, quantity, ordered on, substitute offered, substitute accepted)
SEED_CUSTOMER_ORDERS = [
    ("ACME", "ABC-100", 60, date(2026, 6, 15), True, True),
    ("ACME", "ABC-200", 30, date(2026, 9, 8), False, None),
    ("Hurtownia Delta", "ABC-100", 300, date(2026, 8, 20), False, None),
    ("Technika Omega", "XYZ-300", 100, date(2026, 7, 1), True, False),
]


def _ids(table: str, column: str, values: set[str]) -> dict[str, int]:
    """Ids of the rows whose `column` is in `values`; every value must exist."""
    statement = sa.text(f"SELECT {column}, id FROM {table} WHERE {column} IN :values")
    statement = statement.bindparams(sa.bindparam("values", expanding=True))
    rows = op.get_bind().execute(statement, {"values": sorted(values)})
    found: dict[str, int] = {value: row_id for value, row_id in rows}
    missing = values - found.keys()
    if missing:
        raise RuntimeError(f"{table}: no rows for {sorted(missing)}")
    return found


def upgrade() -> None:
    substitutes = op.create_table(
        "product_substitutes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("substitute_product_id", sa.Integer(), nullable=False),
        sa.Column("compatibility", sa.String(length=30), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["substitute_product_id"], ["products.id"]),
        sa.UniqueConstraint(
            "product_id",
            "substitute_product_id",
            name="uq_product_substitutes_product_id_substitute_product_id",
        ),
        sa.CheckConstraint(
            "compatibility IN ('full', 'partial')", name="ck_product_substitutes_compatibility"
        ),
        sa.CheckConstraint(
            "product_id <> substitute_product_id", name="ck_product_substitutes_not_self"
        ),
    )

    offers = op.create_table(
        "supplier_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("supplier_name", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.CheckConstraint("quantity > 0", name="ck_supplier_offers_quantity"),
        sa.CheckConstraint("lead_time_days >= 0", name="ck_supplier_offers_lead_time_days"),
    )

    orders = op.create_table(
        "customer_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("ordered_on", sa.Date(), nullable=False),
        sa.Column("substitute_offered", sa.Boolean(), nullable=False),
        sa.Column("substitute_accepted", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.CheckConstraint("quantity > 0", name="ck_customer_orders_quantity"),
        sa.CheckConstraint(
            "(substitute_accepted IS NULL) = (NOT substitute_offered)",
            name="ck_customer_orders_substitute_accepted_with_offered",
        ),
    )

    op.create_table(
        "inquiry_orchestrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inquiry_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("analysis_version", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("orchestrated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["trace_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("inquiry_id", name="uq_inquiry_orchestrations_inquiry_id"),
        sa.CheckConstraint(
            "status IN ('completed', 'partial', 'failed')",
            name="ck_inquiry_orchestrations_status",
        ),
    )
    op.create_index("ix_inquiry_orchestrations_run_id", "inquiry_orchestrations", ["run_id"])

    products = sa.table(
        "products",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("list_price", sa.Numeric()),
        sa.column("stock_quantity", sa.Integer()),
    )
    op.bulk_insert(products, SEED_PRODUCTS)

    product_codes = (
        {code for row in SEED_SUBSTITUTES for code in row[:2]}
        | {row[0] for row in SEED_SUPPLIER_OFFERS}
        | {row[1] for row in SEED_CUSTOMER_ORDERS}
    )
    product_ids = _ids("products", "code", product_codes)
    customer_ids = _ids("customers", "name", {row[0] for row in SEED_CUSTOMER_ORDERS})

    op.bulk_insert(
        substitutes,
        [
            {
                "product_id": product_ids[code],
                "substitute_product_id": product_ids[substitute],
                "compatibility": compatibility,
                "note": note,
            }
            for code, substitute, compatibility, note in SEED_SUBSTITUTES
        ],
    )
    op.bulk_insert(
        offers,
        [
            {
                "product_id": product_ids[code],
                "supplier_name": supplier,
                "quantity": quantity,
                "lead_time_days": lead_time_days,
            }
            for code, supplier, quantity, lead_time_days in SEED_SUPPLIER_OFFERS
        ],
    )
    op.bulk_insert(
        orders,
        [
            {
                "customer_id": customer_ids[customer],
                "product_id": product_ids[code],
                "quantity": quantity,
                "ordered_on": ordered_on,
                "substitute_offered": offered,
                "substitute_accepted": accepted,
            }
            for customer, code, quantity, ordered_on, offered, accepted in SEED_CUSTOMER_ORDERS
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_inquiry_orchestrations_run_id", table_name="inquiry_orchestrations")
    op.drop_table("inquiry_orchestrations")
    op.drop_table("customer_orders")
    op.drop_table("supplier_offers")
    op.drop_table("product_substitutes")
    delete_products = sa.text("DELETE FROM products WHERE code IN :codes").bindparams(
        sa.bindparam("codes", value=[p["code"] for p in SEED_PRODUCTS], expanding=True)
    )
    op.execute(delete_products)
