#!/usr/bin/env python3
r"""
db_cli.py — Petit outil console pour parcourir la base MySQL

Fonctionnalités clés:
- test: vérifie la connexion MySQL
- list: liste des produits d'une table, filtrable par marque
- brands: récapitulatif des marques par table
- export: exporte une sélection vers un fichier JSON

Exemples PowerShell:
	python -m database.db_cli test
	python -m database.db_cli list --table serveurs --brand HP --limit 5
	python -m database.db_cli brands --table serveurs
	python -m database.db_cli export --table serveurs --brand HP --out hp_serveurs.json
"""

import argparse
import json
from datetime import datetime
from typing import Optional

import mysql.connector

import os
import sys

# Permet l'exécution directe du script (python .\database\db_cli.py ...)
# en ajoutant le dossier racine du projet au PYTHONPATH avant les imports de package.
_CURR_DIR = os.path.dirname(__file__)
_ROOT_DIR = os.path.abspath(os.path.join(_CURR_DIR, os.pardir))
if _ROOT_DIR not in sys.path:
		sys.path.insert(0, _ROOT_DIR)

from database.config import DB_CONFIG


VALID_TABLES = {"serveurs", "stockage", "imprimantes_scanners"}


def _connect():
	cn = mysql.connector.connect(**DB_CONFIG)
	return cn


def cmd_test() -> int:
	try:
		cn = _connect()
		cn.close()
		print(f"✅ Connexion MySQL OK (db={DB_CONFIG.get('database')})")
		return 0
	except Exception as e:
		print(f"❌ Connexion MySQL échouée: {e}")
		return 1


def cmd_list(table: str, brand: Optional[str], limit: int) -> int:
	if table not in VALID_TABLES:
		print(f"❌ Table invalide: {table}. Choisir parmi {sorted(VALID_TABLES)}")
		return 2
	try:
		cn = _connect()
		cur = cn.cursor(dictionary=True)
		if brand:
			cur.execute(
				f"""
				SELECT id, brand, name, sku,
					   JSON_LENGTH(tech_specs) AS spec_keys,
					   is_active, DATE_FORMAT(scraped_at, '%Y-%m-%d %H:%i') AS scraped_at,
					   LEFT(link, 128) AS link
				FROM {table}
				WHERE brand = %s
				ORDER BY id DESC
				LIMIT %s
				""",
				(brand, limit),
			)
		else:
			cur.execute(
				f"""
				SELECT id, brand, name, sku,
					   JSON_LENGTH(tech_specs) AS spec_keys,
					   is_active, DATE_FORMAT(scraped_at, '%Y-%m-%d %H:%i') AS scraped_at,
					   LEFT(link, 128) AS link
				FROM {table}
				ORDER BY id DESC
				LIMIT %s
				""",
				(limit,),
			)
		rows = cur.fetchall()
		cur.close()
		cn.close()
		if not rows:
			print("(aucun résultat)")
			return 0
		print(json.dumps(rows, indent=2, ensure_ascii=False))
		return 0
	except Exception as e:
		print(f"❌ Erreur list: {e}")
		return 1


def cmd_brands(table: str) -> int:
	if table not in VALID_TABLES:
		print(f"❌ Table invalide: {table}. Choisir parmi {sorted(VALID_TABLES)}")
		return 2
	try:
		cn = _connect()
		cur = cn.cursor()
		cur.execute(
			f"SELECT brand, COUNT(*) AS cnt FROM {table} GROUP BY brand ORDER BY cnt DESC, brand ASC"
		)
		rows = cur.fetchall()
		cur.close()
		cn.close()
		for brand, cnt in rows:
			print(f"{brand}: {cnt}")
		if not rows:
			print("(aucune marque)")
		return 0
	except Exception as e:
		print(f"❌ Erreur brands: {e}")
		return 1


def cmd_export(table: str, brand: Optional[str], out: str) -> int:
	if table not in VALID_TABLES:
		print(f"❌ Table invalide: {table}. Choisir parmi {sorted(VALID_TABLES)}")
		return 2
	try:
		cn = _connect()
		cur = cn.cursor(dictionary=True)
		if brand:
			cur.execute(
				f"SELECT * FROM {table} WHERE brand = %s ORDER BY id DESC",
				(brand,),
			)
		else:
			cur.execute(f"SELECT * FROM {table} ORDER BY id DESC")
		rows = cur.fetchall()
		cur.close()
		cn.close()
		# Convertir JSON string -> dict pour tech_specs
		for r in rows:
			ts = r.get("tech_specs")
			if isinstance(ts, str):
				try:
					r["tech_specs"] = json.loads(ts)
				except Exception:
					r["tech_specs"] = {}
		with open(out, "w", encoding="utf-8") as f:
			json.dump(rows, f, ensure_ascii=False, indent=2)
		print(f"✅ Exporté {len(rows)} lignes → {out}")
		return 0
	except Exception as e:
		print(f"❌ Erreur export: {e}")
		return 1


def build_parser():
	p = argparse.ArgumentParser(description="CLI MySQL pour parcourir la base de scraping")
	sub = p.add_subparsers(dest="cmd", required=True)

	sub.add_parser("test", help="Vérifier la connexion MySQL")

	p_list = sub.add_parser("list", help="Lister des produits")
	p_list.add_argument("--table", required=True, choices=sorted(VALID_TABLES))
	p_list.add_argument("--brand", required=False)
	p_list.add_argument("--limit", type=int, default=10)

	p_brands = sub.add_parser("brands", help="Lister les marques et leurs volumes")
	p_brands.add_argument("--table", required=True, choices=sorted(VALID_TABLES))

	p_export = sub.add_parser("export", help="Exporter vers un JSON")
	p_export.add_argument("--table", required=True, choices=sorted(VALID_TABLES))
	p_export.add_argument("--brand", required=False)
	p_export.add_argument("--out", required=False, default=None)

	return p


def main():
	parser = build_parser()
	args = parser.parse_args()

	if args.cmd == "test":
		return cmd_test()
	if args.cmd == "list":
		return cmd_list(args.table, args.brand, args.limit)
	if args.cmd == "brands":
		return cmd_brands(args.table)
	if args.cmd == "export":
		out = args.out or f"export_{args.table}_{(args.brand or 'all').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
		return cmd_export(args.table, args.brand, out)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

 