import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os

def create_database():
    # Connect to default 'postgres' database
    try:
        con = psycopg2.connect(
            dbname='postgres',
            user='postgres',
            host='localhost',
            password='postgres',
            port='5432'
        )
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()
        
        # Check if exists
        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'transmax'")
        exists = cur.fetchone()
        
        if not exists:
            print("Database 'transmax' not found. Creating...")
            cur.execute('CREATE DATABASE transmax')
            print("Database 'transmax' created successfully.")
        else:
            print("Database 'transmax' already exists.")
            
        cur.close()
        con.close()
        
    except Exception as e:
        print(f"Error creating database: {e}")

if __name__ == "__main__":
    create_database()
