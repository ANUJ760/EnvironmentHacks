"""Retain immutable station-reading membership across refreshes and cities."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "air_revision_observations",
        sa.Column(
            "revision_id", sa.Uuid(), sa.ForeignKey("dataset_revisions.id"), primary_key=True
        ),
        sa.Column(
            "observation_id", sa.Uuid(), sa.ForeignKey("air_observations.id"), primary_key=True
        ),
    )
    op.execute("INSERT INTO air_revision_observations SELECT revision_id,id FROM air_observations")
    op.execute("""CREATE FUNCTION guard_air_membership() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS(SELECT 1 FROM city_snapshots WHERE COALESCE(OLD.revision_id,NEW.revision_id)=ANY(dataset_revision_ids)) THEN
        RAISE EXCEPTION 'published air membership is immutable';
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$""")
    op.execute(
        "CREATE TRIGGER guard_air_membership BEFORE INSERT OR UPDATE OR DELETE ON air_revision_observations FOR EACH ROW EXECUTE FUNCTION guard_air_membership()"
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS(SELECT 1 FROM air_revision_observations)"))
        .scalar()
    ):
        raise RuntimeError("Nonempty source membership: downgrade requires reviewed restore")
    op.drop_table("air_revision_observations")
    op.execute("DROP FUNCTION guard_air_membership()")
