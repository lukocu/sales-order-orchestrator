"""One offer per supplier and product.

Recommendation option ids and supplier costs are keyed by (supplier, product), so two offers
of one supplier for one product would collide.

Revision ID: 0010_supplier_offer_unique
Revises: 0009_recommendation_data
Create Date: 2026-11-11

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_supplier_offer_unique"
down_revision: str | Sequence[str] | None = "0009_recommendation_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "uq_supplier_offers_product_id_supplier_name"


def upgrade() -> None:
    op.create_unique_constraint(CONSTRAINT, "supplier_offers", ["product_id", "supplier_name"])


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "supplier_offers", type_="unique")
