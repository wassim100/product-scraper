import argparse
from typing import Optional
import os
import sys

# Ensure project root is on sys.path for absolute imports like 'database.mysql_connector'
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from database.mysql_connector import MySQLConnector
import mysql.connector


def connect_db() -> MySQLConnector:
    db = MySQLConnector()
    # Ensure DB exists and connect
    db.create_database()
    if not db.connect():
        raise SystemExit("Failed to connect to MySQL. Check database/config.py settings and server status.")
    # Ensure tables exist (no-op if already created)
    db.create_tables()
    return db


def cmd_summary(db: MySQLConnector):
    conn = db.connection
    cur = conn.cursor()
    tables = ["serveurs", "stockage", "imprimantes_scanners"]
    print("Summary (total/active/inactive):")
    for t in tables:
        cur.execute(f"SELECT COUNT(*), SUM(is_active=1) FROM {t}")
        total, active = cur.fetchone()
        active = active or 0
        inactive = (total or 0) - active
        print(f"- {t}: {total} / {active} / {inactive}")
    cur.close()


def cmd_count(db: MySQLConnector, table: str, brand: Optional[str]):
    conn = db.connection
    cur = conn.cursor()
    if brand:
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE brand = %s", (brand,))
    else:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
    (count,) = cur.fetchone()
    print(count)
    cur.close()


def cmd_brands(db: MySQLConnector, table: str):
    conn = db.connection
    cur = conn.cursor()
    cur.execute(
        f"SELECT brand, COUNT(*), SUM(is_active=1) AS active FROM {table} GROUP BY brand ORDER BY COUNT(*) DESC"
    )
    rows = cur.fetchall()
    print("brand,total,active")
    for brand, total, active in rows:
        print(f"{brand},{total},{active or 0}")
    cur.close()


def cmd_sample(db: MySQLConnector, table: str, limit: int, brand: Optional[str]):
    conn = db.connection
    cur = conn.cursor(dictionary=True)
    if brand:
        cur.execute(
            f"""
            SELECT id, brand, sku, name, is_active, last_seen, scraped_at
            FROM {table}
            WHERE brand = %s
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (brand, limit),
        )
    else:
        cur.execute(
            f"""
            SELECT id, brand, sku, name, is_active, last_seen, scraped_at
            FROM {table}
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (limit,),
        )
    rows = cur.fetchall()
    for r in rows:
        print(
            f"#{r['id']} | {r['brand']} | SKU={r['sku'] or ''} | {r['name'][:70]} | active={r['is_active']} | last_seen={r['last_seen']} | scraped_at={r['scraped_at']}"
        )
    cur.close()


def cmd_schema(db: MySQLConnector, table: str):
    conn = db.connection
    cur = conn.cursor()
    cur.execute(f"SHOW CREATE TABLE {table}")
    _, create_sql = cur.fetchone()
    print(create_sql)
    cur.close()


def cmd_columns(db: MySQLConnector, table: str):
    conn = db.connection
    cur = conn.cursor()
    cur.execute(f"SHOW COLUMNS FROM {table}")
    cols = cur.fetchall()
    print("Field,Type,Null,Key,Default,Extra")
    for field, type_, null, key, default, extra in cols:
        default_str = "" if default is None else str(default)
        print(f"{field},{type_},{null},{key},{default_str},{extra}")
    cur.close()


def cmd_rows(db: MySQLConnector, table: str, limit: int, brand: Optional[str], with_specs: bool):
    conn = db.connection
    cur = conn.cursor(dictionary=True)
    base_cols = [
        "id",
        "brand",
        "sku",
        "name",
        "link",
        "datasheet_link",
        "ai_processed",
        "is_active",
        "last_seen",
        "scraped_at",
    ]
    select_cols = ", ".join(base_cols + (["tech_specs"] if with_specs else []))
    if brand:
        cur.execute(
            f"SELECT {select_cols} FROM {table} WHERE brand = %s ORDER BY updated_at DESC LIMIT %s",
            (brand, limit),
        )
    else:
        cur.execute(
            f"SELECT {select_cols} FROM {table} ORDER BY updated_at DESC LIMIT %s",
            (limit,),
        )
    rows = cur.fetchall()
    header = base_cols + (["tech_specs"] if with_specs else [])
    print(" | ".join(header))
    for r in rows:
        vals = []
        for c in base_cols:
            v = r.get(c)
            if v is None:
                vals.append("")
            else:
                s = str(v)
                if len(s) > 180:
                    s = s[:177] + "..."
                vals.append(s)
        if with_specs:
            ts = r.get("tech_specs")
            if ts is None:
                vals.append("")
            else:
                s = str(ts)
                if len(s) > 200:
                    s = s[:197] + "..."
                vals.append(s)
        print(" | ".join(vals))
    cur.close()


def cmd_anomalies(db: MySQLConnector, table: str, brand: Optional[str]):
    conn = db.connection
    cur = conn.cursor()
    where = " WHERE brand = %s" if brand else ""
    params = (brand,) if brand else tuple()

    def one(sql, params_):
        cur.execute(sql, params_)
        return cur.fetchone()[0]

    print(f"Anomalies report for {table}{' (brand=' + brand + ')' if brand else ''}:")
    total = one(f"SELECT COUNT(*) FROM {table}{where}", params)
    sku_missing = one(f"SELECT COUNT(*) FROM {table}{where} AND (sku IS NULL OR sku = '')".replace("WHERE ", "WHERE " if brand else "WHERE 1=1 AND "), params)
    linkhash_missing = one(f"SELECT COUNT(*) FROM {table}{where} AND (link_hash IS NULL OR link_hash = '')".replace("WHERE ", "WHERE " if brand else "WHERE 1=1 AND "), params)
    datasheet_missing = one(f"SELECT COUNT(*) FROM {table}{where} AND (datasheet_link IS NULL OR datasheet_link = '')".replace("WHERE ", "WHERE " if brand else "WHERE 1=1 AND "), params)
    ai_zero = one(f"SELECT COUNT(*) FROM {table}{where} AND (ai_processed = 0 OR ai_processed IS NULL)".replace("WHERE ", "WHERE " if brand else "WHERE 1=1 AND "), params)

    # JSON checks; use TRY/EXCEPT-friendly SQL to avoid errors if JSON invalid
    tech_null = one(f"SELECT COUNT(*) FROM {table}{where} AND tech_specs IS NULL".replace("WHERE ", "WHERE " if brand else "WHERE 1=1 AND "), params)
    tech_is_string = one(f"SELECT COUNT(*) FROM {table}{where} AND JSON_TYPE(tech_specs) = 'STRING'".replace("WHERE ", "WHERE " if brand else "WHERE 1=1 AND "), params)
    tech_empty_obj = one(f"SELECT COUNT(*) FROM {table}{where} AND JSON_TYPE(tech_specs) IN ('OBJECT','ARRAY') AND IFNULL(JSON_LENGTH(tech_specs),0) = 0".replace("WHERE ", "WHERE " if brand else "WHERE 1=1 AND "), params)

    print(f"- total: {total}")
    print(f"- SKU manquant: {sku_missing}")
    print(f"- link_hash manquant: {linkhash_missing}")
    print(f"- datasheet_link manquant: {datasheet_missing}")
    print(f"- ai_processed=0 ou NULL: {ai_zero}")
    print(f"- tech_specs NULL: {tech_null}")
    print(f"- tech_specs type=STRING: {tech_is_string}")
    print(f"- tech_specs objet/array vide: {tech_empty_obj}")

    # Duplicates by brand+link_hash (ignoring NULL/empty)
    dup_sql = f"""
        SELECT brand, link_hash, COUNT(*)
        FROM {table}
        WHERE link_hash IS NOT NULL AND link_hash <> '' {('AND brand = %s' if brand else '')}
        GROUP BY brand, link_hash
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """
    cur.execute(dup_sql, params if brand else tuple())
    dups = cur.fetchall()
    if dups:
        print("- Doublons (brand, link_hash, count):")
        for b, lh, c in dups:
            print(f"  • {b}, {lh[:8]}..., {c}")
    else:
        print("- Doublons link_hash: 0")

    cur.close()


def main():
    parser = argparse.ArgumentParser(description="Read-only DB CLI for scraper data")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("summary", help="Show totals/active/inactive per table")

    p_count = sub.add_parser("count", help="Count rows in a table (optional by brand)")
    p_count.add_argument("table", choices=["serveurs", "stockage", "imprimantes_scanners"]) 
    p_count.add_argument("--brand", help="Filter by brand")

    p_brands = sub.add_parser("brands", help="Counts per brand in a table")
    p_brands.add_argument("table", choices=["serveurs", "stockage", "imprimantes_scanners"]) 

    p_sample = sub.add_parser("sample", help="Show latest N rows of a table")
    p_sample.add_argument("table", choices=["serveurs", "stockage", "imprimantes_scanners"]) 
    p_sample.add_argument("--limit", type=int, default=10)
    p_sample.add_argument("--brand", help="Filter by brand")

    p_schema = sub.add_parser("schema", help="Show CREATE TABLE for a table")
    p_schema.add_argument("table", choices=["serveurs", "stockage", "imprimantes_scanners"]) 

    p_cols = sub.add_parser("columns", help="List columns of a table")
    p_cols.add_argument("table", choices=["serveurs", "stockage", "imprimantes_scanners"]) 

    p_rows = sub.add_parser("rows", help="Show rows from a table (optionally by brand)")
    p_rows.add_argument("table", choices=["serveurs", "stockage", "imprimantes_scanners"]) 
    p_rows.add_argument("--limit", type=int, default=10)
    p_rows.add_argument("--brand", help="Filter by brand")
    p_rows.add_argument("--with-specs", action="store_true", help="Include tech_specs column (truncated)")

    p_anom = sub.add_parser("anomalies", help="Show data quality anomalies for a table")
    p_anom.add_argument("table", choices=["serveurs", "stockage", "imprimantes_scanners"]) 
    p_anom.add_argument("--brand", help="Optional brand filter")

    args = parser.parse_args()

    db = connect_db()
    try:
        if args.cmd == "summary":
            cmd_summary(db)
        elif args.cmd == "count":
            cmd_count(db, args.table, args.brand)
        elif args.cmd == "brands":
            cmd_brands(db, args.table)
        elif args.cmd == "sample":
            cmd_sample(db, args.table, args.limit, args.brand)
        elif args.cmd == "schema":
            cmd_schema(db, args.table)
        elif args.cmd == "columns":
            cmd_columns(db, args.table)
        elif args.cmd == "rows":
            cmd_rows(db, args.table, args.limit, getattr(args, "brand", None), getattr(args, "with_specs", False))
        elif args.cmd == "anomalies":
            cmd_anomalies(db, args.table, getattr(args, "brand", None))
        else:
            raise SystemExit("Unknown command")
    finally:
        db.close()


if __name__ == "__main__":
    main()
