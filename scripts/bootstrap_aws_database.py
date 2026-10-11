"""One-off private ECS administrator task for RDS PostGIS and runtime roles.

Requires DB_ADMIN_SECRET_ARN, DB_HOST and DB_RUNTIME_SECRET_ARNS (JSON map).
Run before migrations, then again with --grants after migrations. Passwords
remain in memory and Secrets Manager; stdout never contains connection URIs.
"""

import argparse
import json
import os
import secrets
from urllib.parse import quote

import boto3
import psycopg
from psycopg import sql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grants", action="store_true")
    args = parser.parse_args()
    client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])
    admin = json.loads(
        client.get_secret_value(SecretId=os.environ["DB_ADMIN_SECRET_ARN"])["SecretString"]
    )
    host = os.environ["DB_HOST"]
    destinations = json.loads(os.environ["DB_RUNTIME_SECRET_ARNS"])
    with psycopg.connect(
        host=host,
        dbname="ecotwin",
        user=admin["username"],
        password=admin["password"],
        sslmode="require",
        autocommit=True,
    ) as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        if not args.grants:
            for kind, arn in destinations.items():
                role = "ecotwin_" + kind
                if connection.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)
                ).fetchone():
                    client.get_secret_value(SecretId=arn)
                    continue
                password = secrets.token_urlsafe(36)
                connection.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE"
                    ).format(sql.Identifier(role), sql.Literal(password))
                )
                connection.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE ecotwin TO {}").format(sql.Identifier(role))
                )
                connection.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role))
                )
                client.put_secret_value(
                    SecretId=arn,
                    SecretString=f"postgresql+psycopg://{role}:{quote(password, safe='')}@{host}:5432/ecotwin?sslmode=require",
                )
            connection.execute("GRANT CREATE ON SCHEMA public TO ecotwin_migrate")
            print("PostGIS installed; independent database roles and secrets provisioned")
        else:
            connection.execute(
                "GRANT SELECT ON ALL TABLES IN SCHEMA public TO ecotwin_api, ecotwin_worker, ecotwin_ingest"
            )
            connection.execute(
                "GRANT INSERT, UPDATE ON scenarios, scenario_edits, simulation_jobs, user_accounts, audit_events TO ecotwin_api"
            )
            connection.execute("GRANT DELETE ON scenario_edits TO ecotwin_api")
            connection.execute(
                "GRANT INSERT, UPDATE ON simulation_jobs, simulation_results, audit_events TO ecotwin_worker"
            )
            connection.execute(
                "GRANT INSERT, UPDATE ON cities, dataset_revisions, import_runs, geo_features, landcover_cells, weather_hours, air_stations, air_observations, air_revision_observations, facility_profiles, city_snapshots TO ecotwin_ingest"
            )
            connection.execute(
                "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ecotwin_api, ecotwin_worker, ecotwin_ingest"
            )
            print("Runtime grants applied")


if __name__ == "__main__":
    main()
