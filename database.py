import pyodbc
import os
from tabulate import tabulate


def get_suppliers():
    """Vrátí seznam dostupných dodavatelů"""
    return [("161784", "api (161784)")]  # Prozatím jen jeden dodavatel

def get_products(supplier_code, limit=10):
    """
    Načte produkty pro překlad
    Args:
        supplier_code: kód dodavatele (např. '161784')
        limit: počet produktů k načtení
    Returns:
        list: seznam tuple (SivCode, SivName)
    """
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        table = os.getenv('DB_TABLE', '')
        query = f"""
            SELECT TOP {limit} SivCode, SivName 
            FROM {table}
            WHERE SivComId = ? AND (SivPLNote IS NULL OR SivPLNote = '')
        """
        cursor.execute(query, (supplier_code,))
        return cursor.fetchall()
    except Exception as e:
        print(f"[ERROR] Chyba při načítání produktů: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def update_product_note(siv_code, note_text):
    """
    Uloží překlad do databáze
    Args:
        siv_code: kód produktu
        note_text: přeložený text
    """
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        table = os.getenv('DB_TABLE', '')
        query = f"UPDATE {table} SET SivPLNote = ? WHERE SivCode = ?"
        cursor.execute(query, (note_text, siv_code))
        conn.commit()
        print(f"[SUCCESS] Uložen překlad pro produkt {siv_code}")
    except Exception as e:
        print(f"[ERROR] Chyba při ukládání překladu: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def connect_to_db():
    from dotenv import load_dotenv
    load_dotenv()
    server = os.getenv('DB_SERVER', '')
    database = os.getenv('DB_DATABASE', '')
    username = os.getenv('DB_USERNAME', '')
    password = os.getenv('DB_PASSWORD', '')
    table = os.getenv('DB_TABLE', '')

    # Debug print connection details with more visibility
    print("\n[DEBUG] Attempting database connection with:")
    print("=" * 50)
    print(f"  Server:    '{server}'")
    print(f"  Database:  '{database}'")
    print(f"  Username:  '{username}'")
    print(f"  Table:     '{table if table else '<default table>'}'")
    print(f"  Password:  {'*****' if password else '<not set>'}")
    print("=" * 50)

    if not all([server, database, username, password]):
        missing = []
        if not server: missing.append("DB_SERVER")
        if not database: missing.append("DB_DATABASE")
        if not username: missing.append("DB_USERNAME")
        if not password: missing.append("DB_PASSWORD")
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        print(f"[ERROR] {error_msg}")
        raise Exception(error_msg)

    try:
        conn_str = (
            f'DRIVER={{SQL Server}};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'UID={username};'
            f'PWD={password}'
        )

        print("[DEBUG] Connection string:", conn_str.replace(password, '*****'))

        # Add connection timeout and other parameters
        conn_str += ';Connection Timeout=30;'

        print("[DEBUG] Attempting to connect...")
        conn = pyodbc.connect(conn_str)

        # Test the connection immediately
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        if cursor.fetchone()[0] == 1:
            print("[DEBUG] Connection test successful")
        cursor.close()

        print("[SUCCESS] Database connection established")
        return conn

    except pyodbc.InterfaceError as e:
        error_msg = f"Interface error (check driver): {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise Exception(error_msg)
    except pyodbc.OperationalError as e:
        error_msg = f"Operational error (server unavailable/wrong credentials): {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise Exception(error_msg)
    except pyodbc.DatabaseError as e:
        error_msg = f"Database error (permissions/configuration): {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Unexpected connection error: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise Exception(error_msg)

def diagnose_database(conn):
    """Diagnose the database structure and content with sample data"""
    cursor = conn.cursor()
    try:
        # Get all tables in the database
        cursor.tables()
        tables = [row.table_name for row in cursor.fetchall()
                  if row.table_type == 'TABLE' and not row.table_name.startswith('sys')]

        if not tables:
            print("[WARNING] No tables found in the database")
            return []

        # Default to first table if DB_TABLE not set
        table = os.getenv('DB_TABLE', tables[0])
        if table not in tables:
            print(f"[WARNING] Table '{table}' not found, using first available table")
            table = tables[0]

        print(f"\n[DIAGNOSTIC] Analyzing table: {table}")

        # Get column information
        cursor.columns(table=table)
        columns = [col.column_name for col in cursor.fetchall()]

        if not columns:
            print("[WARNING] No columns found in the table")
            return []

        # 1. Basic table structure info
        structure_results = []
        for column in columns:
            cursor.execute(f"""
                SELECT 
                    DATA_TYPE,
                    COUNT({column}),
                    COUNT(CASE WHEN {column} IS NULL THEN 1 END),
                    (SELECT TOP 1 {column} FROM {table} WHERE {column} IS NOT NULL ORDER BY NEWID())
                FROM INFORMATION_SCHEMA.COLUMNS
                CROSS JOIN {table}
                WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
                GROUP BY DATA_TYPE
            """, (table, column))

            row = cursor.fetchone()
            if row:
                structure_results.append({
                    'Column': column,
                    'Type': row[0],
                    'Non-Null Count': row[1],
                    'Null Count': row[2],
                    'Sample Value': str(row[3])[:50] + ('...' if len(str(row[3])) > 50 else '')
                })

        print("\n[TABLE STRUCTURE]")
        print(tabulate(structure_results, headers="keys", tablefmt="grid"))

        # 2. Sample rows with SivCode = 161784
        if 'SivCode' in columns:
            try:
                cursor.execute(f"""
                    SELECT TOP 2 * 
                    FROM {table} 
                    WHERE SivCode = '161784'
                """)
                sample_rows = cursor.fetchall()

                if sample_rows:
                    print("\n[SAMPLE ROWS WHERE SivCode = 161784]")
                    # Get column names for headers
                    col_names = [column[0] for column in cursor.description]
                    # Prepare data for display (truncate long values)
                    display_data = []
                    for row in sample_rows:
                        display_row = {}
                        for i, value in enumerate(row):
                            display_row[col_names[i]] = str(value)[:50] + ('...' if len(str(value)) > 50 else '')
                        display_data.append(display_row)
                    print(tabulate(display_data, headers="keys", tablefmt="grid"))
                else:
                    print("\n[INFO] No rows found with SivCode = 161784")
            except Exception as e:
                print(f"\n[WARNING] Couldn't fetch sample rows: {str(e)}")

        # 3. Random sample of 5 rows
        try:
            cursor.execute(f"SELECT TOP 5 * FROM {table} ORDER BY NEWID()")
            random_rows = cursor.fetchall()

            if random_rows:
                print("\n[RANDOM SAMPLE ROWS]")
                col_names = [column[0] for column in cursor.description]
                display_data = []
                for row in random_rows:
                    display_row = {}
                    for i, value in enumerate(row):
                        display_row[col_names[i]] = str(value)[:50] + ('...' if len(str(value)) > 50 else '')
                    display_data.append(display_row)
                print(tabulate(display_data, headers="keys", tablefmt="grid"))
        except Exception as e:
            print(f"\n[WARNING] Couldn't fetch random rows: {str(e)}")

        return structure_results

    except Exception as e:
        print(f"[ERROR] Database diagnosis failed: {str(e)}")
        raise Exception(f"Database diagnosis failed: {str(e)}")
    finally:
        cursor.close()
        print("[DEBUG] Diagnosis cursor closed")

if __name__ == "__main__":
    # Example usage
    try:
        conn = connect_to_db()
        diagnose_database(conn)
        conn.close()
    except Exception as e:
        print(f"[ERROR] Main execution failed: {str(e)}")