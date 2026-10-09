"""Initial schema; bootstrap PostGIS separately as database administrator."""

from alembic import op
from sqlalchemy import text

from migrations import initial_schema  # noqa: F401
from migrations.initial_base import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if not connection.execute(
        text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='postgis')")
    ).scalar():
        raise RuntimeError("Bootstrap CREATE EXTENSION postgis with the schema administrator first")
    Base.metadata.create_all(connection)
    op.execute("""CREATE FUNCTION ecotwin_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'published scientific input/result is immutable'; END $$""")
    for table, condition in [
        ("dataset_revisions", "OLD.status = 'READY'"),
        ("city_snapshots", "OLD.status = 'PUBLISHED'"),
        ("simulation_results", "true"),
    ]:
        op.execute(
            f"CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW WHEN ({condition}) EXECUTE FUNCTION ecotwin_immutable()"
        )
    op.execute("""CREATE FUNCTION ecotwin_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS(SELECT 1 FROM unnest(NEW.dataset_revision_ids) r LEFT JOIN dataset_revisions d ON d.id=r WHERE d.id IS NULL OR d.status <> 'READY' OR d.city_id <> NEW.city_id) THEN
        RAISE EXCEPTION 'snapshot requires ready same-city revisions';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute(
        "CREATE TRIGGER snapshot_guard BEFORE INSERT ON city_snapshots FOR EACH ROW EXECUTE FUNCTION ecotwin_snapshot_guard()"
    )
    for table in [
        "geo_features",
        "landcover_cells",
        "weather_hours",
        "air_observations",
        "facility_profiles",
    ]:
        op.execute(f"""CREATE FUNCTION guard_{table}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS(SELECT 1 FROM city_snapshots WHERE COALESCE(OLD.revision_id,NEW.revision_id)=ANY(dataset_revision_ids)) THEN
            RAISE EXCEPTION 'snapshot source rows are immutable';
          END IF;
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END $$""")
        op.execute(
            f"CREATE TRIGGER guard_{table} BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION guard_{table}()"
        )


def downgrade():
    # A rollback deliberately refuses to destroy operator datasets or saved results.
    connection = op.get_bind()
    for table in Base.metadata.sorted_tables:
        if connection.execute(
            text(f'SELECT EXISTS(SELECT 1 FROM "{table.name}" LIMIT 1)')
        ).scalar():
            raise RuntimeError(
                "Nonempty schema: restore/review required; destructive downgrade refused"
            )
    Base.metadata.drop_all(connection)
    for table in [
        "geo_features",
        "landcover_cells",
        "weather_hours",
        "air_observations",
        "facility_profiles",
    ]:
        op.execute(f"DROP FUNCTION guard_{table}()")
    op.execute("DROP FUNCTION ecotwin_snapshot_guard()")
    op.execute("DROP FUNCTION ecotwin_immutable()")
