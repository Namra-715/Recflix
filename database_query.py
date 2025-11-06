#!/usr/bin/env python3
"""
MySQL Database Query Script for Recflix Movie Database
Supports filtering and querying movies with various criteria.
"""

import sys
import subprocess
from typing import Dict, List, Optional, Any


def check_and_install_dependencies():
    """Check if required dependencies are installed and install them if missing."""
    try:
        import mysql.connector
        from mysql.connector import Error
        return mysql.connector, Error
    except ImportError:
        print("=" * 60)
        print("Required dependency 'mysql-connector-python' not found.")
        print("Attempting to install automatically...")
        print("=" * 60)
        
        install_methods = [
            # Method 1: Normal install
            [sys.executable, "-m", "pip", "install", "mysql-connector-python>=8.0.33", "--quiet"],
            # Method 2: User install (for externally-managed environments)
            [sys.executable, "-m", "pip", "install", "--user", "mysql-connector-python>=8.0.33", "--quiet"],
            # Method 3: Break system packages (last resort)
            [sys.executable, "-m", "pip", "install", "--break-system-packages", "mysql-connector-python>=8.0.33", "--quiet"],
        ]
        
        for i, method in enumerate(install_methods, 1):
            try:
                subprocess.check_call(method, stderr=subprocess.DEVNULL)
                print(f"✓ Successfully installed mysql-connector-python (method {i})")
                print()
                
                # Try importing again
                import mysql.connector
                from mysql.connector import Error
                return mysql.connector, Error
            except subprocess.CalledProcessError:
                continue
            except Exception:
                continue
        
        # If all methods failed, provide helpful instructions
        print("\n✗ Automatic installation failed.")
        print("\nPlease install manually using one of these methods:")
        print("\n1. User install (recommended):")
        print("   pip install --user mysql-connector-python")
        print("\n2. Virtual environment (best practice):")
        print("   python3 -m venv venv")
        print("   source venv/bin/activate  # On Windows: venv\\Scripts\\activate")
        print("   pip install mysql-connector-python")
        print("\n3. System install (if you have permissions):")
        print("   pip install --break-system-packages mysql-connector-python")
        print("\nOr install from requirements.txt:")
        print("   pip install --user -r requirements.txt")
        sys.exit(1)


# Install dependencies if needed
mysql_connector, Error = check_and_install_dependencies()


# ============================================================================
# DATABASE CONFIGURATION - Edit these values to hardcode your MySQL setup
# ============================================================================
USE_HARDCODED_CONFIG = True  # Set to False to be prompted for credentials each time

# MySQL Connection Settings
MYSQL_CONFIG = {
    'host': '35.188.165.105',
    'database': 'Recflix',  # Change this to your database name
    'user': 'namra',  # Change this to your MySQL username
    'password': 'recflixdb',  # Leave empty if no password, or set your password here
    'port': 3306
}
# ============================================================================


class MovieDatabase:
    """Class to handle MySQL database operations for movie queries."""
    
    def __init__(self, host: str, database: str, user: str, password: str, port: int = 3306):
        """
        Initialize database connection.
        
        Args:
            host: MySQL server host
            database: Database name
            user: MySQL username
            password: MySQL password
            port: MySQL port (default: 3306)
        """
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.connection = None
        self.cursor = None
        
        # Define all columns
        self.columns = [
            'id', 'title', 'vote_average', 'vote_count', 'status', 'release_date',
            'revenue', 'runtime', 'budget', 'imdb_id', 'original_language',
            'original_title', 'overview', 'popularity', 'tagline', 'genres',
            'production_companies', 'production_countries', 'spoken_languages',
            'cast', 'director', 'director_of_photography', 'writers', 'producers',
            'music_composer', 'imdb_rating', 'imdb_votes', 'poster_path'
        ]
    
    def connect(self) -> bool:
        """Establish connection to MySQL database."""
        try:
            self.connection = mysql_connector.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port
            )
            if self.connection.is_connected():
                self.cursor = self.connection.cursor(dictionary=True)
                return True
        except Error as e:
            print(f"Error connecting to MySQL database: {e}")
            return False
    
    def disconnect(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.connection and self.connection.is_connected():
            self.connection.close()
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results.
        
        Args:
            query: SQL query string
            params: Optional tuple of parameters for parameterized queries
            
        Returns:
            List of dictionaries containing query results
        """
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            results = self.cursor.fetchall()
            return results
        except Error as e:
            print(f"Error executing query: {e}")
            return []
    
    def build_filter_query(self, filters: Dict[str, Any], limit: Optional[int] = None) -> tuple:
        """
        Build a SQL query with filters.
        
        Args:
            filters: Dictionary of column names and filter values
            limit: Optional limit on number of results
            
        Returns:
            Tuple of (query_string, params_tuple)
        """
        base_query = "SELECT * FROM movies WHERE 1=1"
        params = []
        conditions = []
        
        for column, value in filters.items():
            if column not in self.columns:
                print(f"Warning: Column '{column}' not recognized. Skipping.")
                continue
            
            if value is None:
                continue
            
            # Handle different filter types
            if isinstance(value, dict):
                # Support operators like {'operator': '>', 'value': 7.5}
                operator = value.get('operator', '=')
                filter_value = value.get('value')
                if filter_value is not None:
                    conditions.append(f"{column} {operator} %s")
                    params.append(filter_value)
            elif isinstance(value, list):
                # Handle comma-separated string columns (like genres, production_countries)
                # Use LIKE with OR conditions to search within comma-separated strings
                if column in ['genres', 'production_countries', 'spoken_languages']:
                    # For comma-separated string columns, use LIKE to find any match (case-insensitive)
                    like_conditions = []
                    for item in value:
                        item_lower = item.lower()
                        # Search for the genre/country with commas on both sides, or at start/end
                        # Handle both with and without spaces around commas
                        like_conditions.append(f"(LOWER({column}) LIKE %s OR LOWER({column}) LIKE %s OR LOWER({column}) LIKE %s OR LOWER({column}) LIKE %s OR LOWER({column}) LIKE %s OR LOWER({column}) LIKE %s OR LOWER({column}) = %s)")
                        params.extend([
                            f"%, {item_lower}, %",  # In middle with spaces: "action, drama, thriller"
                            f"{item_lower}, %",      # At start with space: "action, drama"
                            f"%, {item_lower}",      # At end with space: "drama, action"
                            f",{item_lower},%",      # In middle without spaces: "action,drama,thriller"
                            f"{item_lower},%",       # At start without space: "action,drama"
                            f"%,{item_lower}",       # At end without space: "drama,action"
                            item_lower               # Exact match: "action"
                        ])
                    conditions.append("(" + " OR ".join(like_conditions) + ")")
                else:
                    # For other columns, use IN clause for exact matches (case-insensitive for strings)
                    if column in ['id', 'vote_average', 'vote_count', 'revenue', 'runtime', 'budget', 
                                  'popularity', 'imdb_rating', 'imdb_votes', 'release_date']:
                        # Numeric/date columns - case-sensitive not needed
                        placeholders = ','.join(['%s'] * len(value))
                        conditions.append(f"{column} IN ({placeholders})")
                        params.extend(value)
                    else:
                        # String columns - make case-insensitive
                        placeholders = ','.join(['%s'] * len(value))
                        conditions.append(f"LOWER({column}) IN ({placeholders})")
                        params.extend([v.lower() if isinstance(v, str) else v for v in value])
            elif isinstance(value, str):
                # LIKE for string search (case-insensitive)
                # Special handling for comma-separated string columns
                if column in ['genres', 'production_countries', 'spoken_languages']:
                    # Search for the genre/country within comma-separated string (case-insensitive)
                    value_lower = value.lower()
                    conditions.append(f"(LOWER({column}) LIKE %s OR LOWER({column}) LIKE %s OR LOWER({column}) LIKE %s OR LOWER({column}) LIKE %s OR LOWER({column}) LIKE %s OR LOWER({column}) LIKE %s OR LOWER({column}) = %s)")
                    params.extend([
                        f"%, {value_lower}, %",      # In middle with spaces: "action, drama, thriller"
                        f"{value_lower}, %",         # At start with space: "action, drama"
                        f"%, {value_lower}",         # At end with space: "drama, action"
                        f",{value_lower},%",         # In middle without spaces: "action,drama,thriller"
                        f"{value_lower},%",          # At start without space: "action,drama"
                        f"%,{value_lower}",         # At end without space: "drama,action"
                        value_lower                  # Exact match: "action"
                    ])
                elif '%' in value or '_' in value:
                    # User-provided wildcards - keep as-is but make case-insensitive
                    conditions.append(f"LOWER({column}) LIKE LOWER(%s)")
                    params.append(value)
                else:
                    # Regular string search - case-insensitive
                    conditions.append(f"LOWER({column}) LIKE %s")
                    params.append(f"%{value.lower()}%")
            else:
                # Exact match for numbers, dates, etc. (case-insensitive for strings)
                if column in ['id', 'vote_average', 'vote_count', 'revenue', 'runtime', 'budget', 
                              'popularity', 'imdb_rating', 'imdb_votes', 'release_date']:
                    # Numeric/date columns - no case conversion needed
                    conditions.append(f"{column} = %s")
                    params.append(value)
                else:
                    # String columns - make case-insensitive
                    conditions.append(f"LOWER({column}) = LOWER(%s)")
                    params.append(str(value))
        
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        if limit:
            base_query += f" LIMIT {limit}"
        
        return base_query, tuple(params)
    
    def query_movies(self, filters: Dict[str, Any], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query movies with filters.
        
        Args:
            filters: Dictionary of filters
            limit: Optional limit on number of results
            
        Returns:
            List of movie records
        """
        query, params = self.build_filter_query(filters, limit)
        print(f"\nExecuting query: {query}")
        if params:
            print(f"Parameters: {params}")
        return self.execute_query(query, params)


def get_user_input() -> Dict[str, Any]:
    """Get filter criteria from user via terminal input."""
    filters = {}
    
    print("\n=== Movie Database Query Interface ===")
    print("Enter filter criteria (press Enter to skip):")
    print("Type 'done' when finished entering filters\n")
    
    # Common filters with prompts
    filter_prompts = {
        'title': 'Title (partial match): ',
        'genres': 'Genres (comma-separated): ',
        'production_countries': 'Production Countries (comma-separated): ',
        'director': 'Director: ',
        'cast': 'Cast member: ',
        'vote_average': 'Minimum vote average (e.g., 7.5): ',
        'release_date': 'Release date (YYYY-MM-DD): ',
        'runtime': 'Minimum runtime (minutes): ',
        'imdb_rating': 'Minimum IMDb rating: ',
        'original_language': 'Original language (e.g., en): ',
        'status': 'Status: ',
    }
    
    for column, prompt in filter_prompts.items():
        value = input(prompt).strip()
        if value.lower() == 'done':
            break
        if value:
            # Handle numeric filters
            if column in ['vote_average', 'runtime', 'imdb_rating']:
                try:
                    filters[column] = {'operator': '>=', 'value': float(value)}
                except ValueError:
                    print(f"Invalid number for {column}. Skipping.")
            # Handle list filters
            elif column in ['genres', 'production_countries']:
                items = [item.strip() for item in value.split(',')]
                filters[column] = items
            else:
                filters[column] = value
    
    # Allow custom SQL query
    print("\nOr enter a custom SQL query (press Enter to skip):")
    custom_query = input("SQL Query: ").strip()
    
    if custom_query:
        return {'_custom_query': custom_query}
    
    return filters


def display_results(results: List[Dict[str, Any]], initial_limit: int = 10):
    """Display query results in a formatted way with pagination support."""
    if not results:
        print("\nNo results found.")
        return
    
    total_results = len(results)
    print(f"\n{'='*80}")
    print(f"Found {total_results} result(s)")
    print(f"{'='*80}\n")
    
    # Ask user how many results to display
    if total_results > initial_limit:
        print(f"Showing first {initial_limit} results out of {total_results}.")
        display_input = input(f"How many results to display? (Enter for {initial_limit}, 'all' for all, or a number): ").strip().lower()
        
        if display_input == 'all':
            display_limit = total_results
        elif display_input:
            try:
                display_limit = int(display_input)
                if display_limit < 1:
                    display_limit = initial_limit
                elif display_limit > total_results:
                    display_limit = total_results
            except ValueError:
                display_limit = initial_limit
        else:
            display_limit = initial_limit
    else:
        display_limit = total_results
    
    # Display results
    for idx, movie in enumerate(results[:display_limit], 1):
        print(f"\n--- Movie {idx} ---")
        print(f"ID: {movie.get('id', 'N/A')}")
        print(f"Title: {movie.get('title', 'N/A')}")
        print(f"Original Title: {movie.get('original_title', 'N/A')}")
        print(f"Release Date: {movie.get('release_date', 'N/A')}")
        print(f"Vote Average: {movie.get('vote_average', 'N/A')}")
        print(f"IMDb Rating: {movie.get('imdb_rating', 'N/A')}")
        print(f"Runtime: {movie.get('runtime', 'N/A')} minutes")
        print(f"Director: {movie.get('director', 'N/A')}")
        print(f"Genres: {movie.get('genres', 'N/A')}")
        print(f"Overview: {movie.get('overview', 'N/A')[:200]}..." if movie.get('overview') else "Overview: N/A")
        print("-" * 80)
    
    if total_results > display_limit:
        print(f"\n... and {total_results - display_limit} more result(s) not shown")
    
    # Offer to show more results
    if total_results > display_limit:
        show_more = input("\nShow more results? (y/n): ").strip().lower()
        if show_more == 'y':
            remaining = results[display_limit:]
            print(f"\n{'='*80}")
            print(f"Displaying remaining {len(remaining)} result(s)")
            print(f"{'='*80}\n")
            
            for idx, movie in enumerate(remaining, display_limit + 1):
                print(f"\n--- Movie {idx} ---")
                print(f"ID: {movie.get('id', 'N/A')}")
                print(f"Title: {movie.get('title', 'N/A')}")
                print(f"Original Title: {movie.get('original_title', 'N/A')}")
                print(f"Release Date: {movie.get('release_date', 'N/A')}")
                print(f"Vote Average: {movie.get('vote_average', 'N/A')}")
                print(f"IMDb Rating: {movie.get('imdb_rating', 'N/A')}")
                print(f"Runtime: {movie.get('runtime', 'N/A')} minutes")
                print(f"Director: {movie.get('director', 'N/A')}")
                print(f"Genres: {movie.get('genres', 'N/A')}")
                print(f"Overview: {movie.get('overview', 'N/A')[:200]}..." if movie.get('overview') else "Overview: N/A")
                print("-" * 80)


def main():
    """Main function to run the database query interface."""
    # Get database configuration
    if USE_HARDCODED_CONFIG:
        # Use hardcoded configuration
        host = MYSQL_CONFIG['host']
        database = MYSQL_CONFIG['database']
        user = MYSQL_CONFIG['user']
        password = MYSQL_CONFIG['password']
        port = MYSQL_CONFIG['port']
    else:
        # Prompt for configuration
        print("=== MySQL Database Configuration ===")
        host = input("MySQL Host [localhost]: ").strip() or "localhost"
        database = input("Database Name: ").strip()
        user = input("MySQL Username: ").strip()
        password_input = input("MySQL Password (press Enter if none): ").strip()
        password = password_input if password_input else ""
        port_input = input("MySQL Port [3306]: ").strip()
        port = int(port_input) if port_input else 3306
    
    # Initialize database connection
    db = MovieDatabase(host, database, user, password, port)
    
    if not db.connect():
        print("Failed to connect to database. Exiting.")
        sys.exit(1)
    
    try:
        while True:
            # Get user input
            filters = get_user_input()
            
            if not filters:
                print("No filters provided. Exiting.")
                break
            
            # Handle custom query
            if '_custom_query' in filters:
                results = db.execute_query(filters['_custom_query'])
            else:
                # Get limit
                limit_input = input("\nLimit results (press Enter for no limit): ").strip()
                limit = int(limit_input) if limit_input else None
                
                # Execute query
                results = db.query_movies(filters, limit)
            
            # Display results
            display_results(results)
            
            # Ask if user wants to continue
            continue_query = input("\nRun another query? (y/n): ").strip().lower()
            if continue_query != 'y':
                break
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        db.disconnect()


if __name__ == "__main__":
    main()

