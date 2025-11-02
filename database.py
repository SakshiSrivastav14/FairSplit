import os
import json
from datetime import datetime
from contextlib import contextmanager

USE_DB = 'DATABASE_URL' in os.environ

if USE_DB:
    import psycopg2

@contextmanager
def get_db_connection():
    if not USE_DB:
        raise RuntimeError("Database not configured for local mode.")
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


JSON_FILE = "local_data.json"

def _read_json():
    if not os.path.exists(JSON_FILE):
        return {"groups": [], "templates": []}
    with open(JSON_FILE, "r") as f:
        return json.load(f)

def _write_json(data):
    with open(JSON_FILE, "w") as f:
        json.dump(data, f, indent=2)


def save_group(name, description, category, members, fairness_score, total_amount):
    if USE_DB:
  
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO groups (name, description, category, fairness_score, total_amount)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    (name, description, category, fairness_score, total_amount)
                )
                group_id = cur.fetchone()[0]
                for member in members:
                    cur.execute(
                        """INSERT INTO members (group_id, name, amount)
                           VALUES (%s, %s, %s)""",
                        (group_id, member['name'], member['amount'])
                    )
                return group_id
    else:
        data = _read_json()
        group_id = len(data["groups"]) + 1
        data["groups"].append({
            "id": group_id,
            "name": name,
            "description": description,
            "category": category,
            "created_at": str(datetime.now()),
            "fairness_score": fairness_score,
            "total_amount": total_amount,
            "members": members
        })
        _write_json(data)
        return group_id

def get_all_groups():
    if USE_DB:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, name, description, category, created_at, fairness_score, total_amount
                       FROM groups
                       ORDER BY created_at DESC"""
                )
                groups = []
                for row in cur.fetchall():
                    groups.append({
                        'id': row[0],
                        'name': row[1],
                        'description': row[2],
                        'category': row[3],
                        'created_at': row[4],
                        'fairness_score': float(row[5]) if row[5] else None,
                        'total_amount': float(row[6]) if row[6] else None
                    })
                return groups
    else:
        data = _read_json()
        return data["groups"]

