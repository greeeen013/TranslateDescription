import pyodbc
from dotenv import load_dotenv
import os


def get_database_columns():
    """
    Načte konfiguraci z .env souboru, připojí se k databázi
    a vrátí seznam názvů sloupců z dané tabulky.

    Returns:
        list: Seznam názvů sloupců nebo None při chybě
    """
    # Načtení proměnných z .env souboru
    load_dotenv()

    config = {
        'server': os.getenv('DB_SERVER'),
        'database': os.getenv('DB_DATABASE'),
        'table': os.getenv('DB_TABLE'),
        'username': os.getenv('DB_USERNAME'),
        'password': os.getenv('DB_PASSWORD')
    }

    # Ověření, že všechny proměnné byly načteny
    for key, value in config.items():
        if value is None:
            print(f"❌ Chyba: V .env souboru chybí proměnná {key}")
            return None

    try:
        # Vytvoření connection stringu
        connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={config['server']};"
            f"DATABASE={config['database']};"
            f"UID={config['username']};"
            f"PWD={config['password']}"
        )

        # Připojení k databázi
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()

        # Získání názvů sloupců
        cursor.execute(f"SELECT TOP 0 * FROM {config['table']}")
        columns = [column[0] for column in cursor.description]

        return columns

    except pyodbc.Error as e:
        print(f"❌ Databázová chyba: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()




# Příklad použití
if __name__ == "__main__":
    columns = get_database_columns()

    if columns:
        print(f"📊 Názvy sloupců v tabulce {os.getenv('DB_TABLE')}:")
        for i, column in enumerate(columns, 1):
            print(f"{i}. {column}")
    else:
        print("Nepodařilo se získat sloupce z tabulky")