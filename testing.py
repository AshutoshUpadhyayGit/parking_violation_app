import psycopg2
POSTGRES_CONN = "postgresql://postgres.rkjebswwcflbxwotoocu:parking_system@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(POSTGRES_CONN)
print("Connected to Supabase!")
