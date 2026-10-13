import pyodbc

from BD.config import (
    MSSQL_DATABASE,
    MSSQL_DRIVER,
    MSSQL_PASSWORD,
    MSSQL_SERVER,
    MSSQL_USER,
)

# Тестовый запрос. Первая колонка — название ЖК.
# Поменяйте таблицу и поле на свои.
COMPLEX_QUERY = """
SELECT TOP 10 Name
FROM dbo.Complexes
"""


def _connection_string() -> str:
    parts = [
        f"DRIVER={{{MSSQL_DRIVER}}}",
        f"SERVER={MSSQL_SERVER}",
        f"DATABASE={MSSQL_DATABASE}",
    ]
    if MSSQL_USER.strip():
        parts.append(f"UID={MSSQL_USER}")
        parts.append(f"PWD={MSSQL_PASSWORD}")
    else:
        parts.append("Trusted_Connection=yes")
    return ";".join(parts)


def fetch_names() -> list[str]:
    if not MSSQL_SERVER.strip() or not MSSQL_DATABASE.strip():
        raise RuntimeError("Пропишите MSSQL_SERVER и MSSQL_DATABASE в BD/config.py")
    connection = pyodbc.connect(_connection_string(), timeout=15)
    try:
        cursor = connection.cursor()
        cursor.execute(COMPLEX_QUERY)
        return [str(row[0]).strip() for row in cursor.fetchall() if row[0]]
    finally:
        connection.close()
