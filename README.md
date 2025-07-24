# Product Description Translation Tool

This application is designed to automate the translation of product descriptions from Polish to Czech. It combines web scraping, AI-powered translation, and database operations to streamline the translation process for e-commerce products.

## Key Features
- Scrapes product descriptions and specifications from supplier websites
- Uses AI (DeepSeek-R1-Distill-Llama-70B-free model) for translation
- Stores translations in a database
- Includes batch processing and error handling
- Provides a user-friendly GUI for managing the translation process

> This project was custom-developed for a specific company's needs.

## Requirements to Run the Application

### 1. System Requirements
- Python 3.8 or higher
- Windows OS (recommended due to SQL Server driver compatibility)
- Stable internet connection

### 2. Python Dependencies
- Install required packages using:
  - ```pip install pyodbc requests beautifulsoup4 python-dotenv together tabulate tk```

### 3. Database Configuration
- SQL Server database access
- Create a `.env` file with these variables:
   ```
   DB_SERVER=your_server_ip
   DB_DATABASE=your_database_name
   DB_USERNAME=your_username
   DB_PASSWORD=your_password
   DB_TABLE=your_table_name
   TOGETHER_API_KEY=together_api_key (https://api.together.ai)
   ```

## How to Run
- Execute the main application:
  - ```python main.py```


## Troubleshooting
- If encountering database connection issues, verify your credentials and ODBC driver
- For web scraping failures, check if the supplier's website structure has changed

## Project Structure
- `main.py`: GUI application
- `database.py`: Database operations
- `LLMTranslate.py`: AI translation interface
- `apiScrapeDescriptions.py`: Web scraping functions

