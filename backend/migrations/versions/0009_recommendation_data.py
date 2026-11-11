"""Unit cost of products and supplier offers (for option margins) and the recommendation
result of an inquiry.

Revision ID: 0009_recommendation_data
Revises: 0008_orchestration_checks_ref
Create Date: 2026-11-11

"""

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_recommendation_data"
down_revision: str | Sequence[str] | None = "0008_orchestration_checks_ref"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# product code -> unit cost (PLN net) of own stock
SEED_PRODUCT_COSTS = {
    "ABC-100": Decimal("84.00"),
    "ABC-110": Decimal("90.00"),
    "ABC-200": Decimal("60.00"),
    "XYZ-300": Decimal("170.00"),
    "XYZ-310": Decimal("180.00"),
}

# (supplier, product code) -> purchase price per unit (PLN net)
SEED_OFFER_COSTS = {
    ("Sensortech Polska", "ABC-100"): Decimal("96.00"),
    ("Hydro-Valve", "XYZ-300"): Decimal("185.00"),
}


def upgrade() -> None:
    op.add_column("products", sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True))
    op.add_column("supplier_offers", sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True))

    bind = op.get_bind()
    for code, cost in SEED_PRODUCT_COSTS.items():
        bind.execute(
            sa.text("UPDATE products SET unit_cost = :cost WHERE code = :code"),
            {"cost": cost, "code": code},
        )
    for (supplier, code), cost in SEED_OFFER_COSTS.items():
        bind.execute(
            sa.text(
                """
                UPDATE supplier_offers AS o
                SET unit_cost = :cost
                FROM products AS p
                WHERE p.id = o.product_id AND p.code = :code AND o.supplier_name = :supplier
                """
            ),
            {"cost": cost, "code": code, "supplier": supplier},
        )
    # Rows outside the seed (e.g. left by tests in a local database).
    op.execute("UPDATE products SET unit_cost = round(list_price * 0.7, 2) WHERE unit_cost IS NULL")
    op.execute(
        """
        UPDATE supplier_offers AS o
        SET unit_cost = round(p.list_price * 0.8, 2)
        FROM products AS p
        WHERE p.id = o.product_id AND o.unit_cost IS NULL
        """
    )

    op.alter_column("products", "unit_cost", nullable=False)
    op.alter_column("supplier_offers", "unit_cost", nullable=False)
    op.create_check_constraint("ck_products_unit_cost", "products", "unit_cost > 0")
    op.create_check_constraint("ck_supplier_offers_unit_cost", "supplier_offers", "unit_cost > 0")

    op.create_table(
        "inquiry_recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inquiry_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("analysis_version", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checks_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("orchestrated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("recommended_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["trace_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("inquiry_id", name="uq_inquiry_recommendations_inquiry_id"),
        sa.CheckConstraint(
            "status IN ('completed', 'failed')", name="ck_inquiry_recommendations_status"
        ),
    )
    op.create_index("ix_inquiry_recommendations_run_id", "inquiry_recommendations", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_inquiry_recommendations_run_id", table_name="inquiry_recommendations")
    op.drop_table("inquiry_recommendations")
    op.drop_constraint("ck_supplier_offers_unit_cost", "supplier_offers", type_="check")
    op.drop_constraint("ck_products_unit_cost", "products", type_="check")
    op.drop_column("supplier_offers", "unit_cost")
    op.drop_column("products", "unit_cost")
