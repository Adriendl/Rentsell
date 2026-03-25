"""Initial schema: listings + price_history.

Revision ID: 001
Revises:
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "listings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("dedup_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("city", sa.String(200), nullable=False),
        sa.Column("city_slug", sa.String(200), nullable=False),
        sa.Column("insee_code", sa.String(10), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lng", sa.Float, nullable=False),
        sa.Column("surface", sa.Integer, nullable=False),
        sa.Column("rooms", sa.Integer, nullable=True),
        sa.Column("price", sa.Integer, nullable=False),
        sa.Column("price_sqm", sa.Integer, nullable=True),
        sa.Column("images", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_served_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_listings_city_active",
        "listings",
        ["city_slug"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_listings_price_sqm",
        "listings",
        ["price_sqm"],
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_table(
        "price_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "listing_id",
            sa.String(36),
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Integer, nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("price_history")
    op.drop_index("idx_listings_price_sqm", table_name="listings")
    op.drop_index("idx_listings_city_active", table_name="listings")
    op.drop_table("listings")
