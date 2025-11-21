import psycopg2, os

url = os.getenv("SUPABASE_DB_URL")

try:
    conn = psycopg2.connect(url)
    print("CONNECTED")
except Exception as e:
    print("FAILED:", e)