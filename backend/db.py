import psycopg2
import pyodbc 
import os

def get_connection():
    return psycopg2.connect(
        database=os.getenv("DB_NAME", "camunda"),
        user=os.getenv("DB_USER", "camunda"),
        password=os.getenv("DB_PASSWORD", "camunda"),
        host=os.getenv("DB_HOST", "postgres"),
        port=os.getenv("DB_PORT", "5432")
    )

def get_azure_connection():
    server = os.getenv("AZURE_SQL_SERVER")
    database = os.getenv("AZURE_SQL_DATABASE")
    user = os.getenv("AZURE_SQL_USER")
    password = os.getenv("AZURE_SQL_PASSWORD")

    if not all([server, database, user, password]):
        raise ValueError("Missing AZURE_SQL credentials")

    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{server},1433;"
        f"Database={database};"
        f"Uid={user};"
        f"Pwd={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)
