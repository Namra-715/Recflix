# Recflix
Movie Recommendation System using TMDB Dataset.

## Database Query Script

### Quick Start (Plug & Play)

The `database_query.py` script automatically installs dependencies when run. Just download and run:

```bash
python database_query.py
```

No manual installation needed! The script will automatically install `mysql-connector-python` if it's missing.

### Features

- ✅ **Automatic dependency installation** - No manual setup required
- ✅ **Interactive terminal interface** - Easy filtering and querying
- ✅ **Case-insensitive searches** - Search works regardless of capitalization
- ✅ **Comma-separated value support** - Filter by multiple genres/countries at once
- ✅ **Smart genre/country matching** - Finds movies with comma-separated genres (e.g., "Action, Drama")
- ✅ **Flexible result display** - Choose how many results to show or view all
- ✅ **Custom SQL query support** - Write your own queries if needed
- ✅ **Hardcoded configuration** - Set your MySQL credentials once, use forever
- ✅ **Ready for backend integration** - MovieDatabase class can be imported for API use

### Configuration

#### Hardcoded Configuration (Recommended)

Edit the configuration section at the top of `database_query.py`:

```python
USE_HARDCODED_CONFIG = True  # Set to False to be prompted each time

MYSQL_CONFIG = {
    'host': 'localhost',
    'database': 'Recflix',  # Your database name
    'user': 'root',        # Your MySQL username
    'password': '',        # Leave empty if no password
    'port': 3306
}
```

Once configured, the script connects automatically without prompting for credentials.

#### Interactive Configuration

Set `USE_HARDCODED_CONFIG = False` to be prompted for MySQL credentials each time you run the script.

### Database Schema

The script expects a MySQL table named `movies` with the following columns:

**Basic Info:**
- `id`, `title`, `original_title`, `overview`, `tagline`, `status`

**Ratings & Metrics:**
- `vote_average`, `vote_count`, `popularity`, `imdb_rating`, `imdb_votes`

**Release & Financial:**
- `release_date`, `revenue`, `budget`, `runtime`

**Production:**
- `production_companies`, `production_countries`, `spoken_languages`
- `original_language`, `genres`

**Cast & Crew:**
- `cast`, `director`, `director_of_photography`, `writers`, `producers`, `music_composer`

**Other:**
- `imdb_id`, `poster_path`

### Available Filters

The script supports filtering by:

| Filter | Type | Example | Notes |
|--------|------|---------|-------|
| **Title** | Text search | `Inception` | Case-insensitive partial match |
| **Genres** | Comma-separated | `Action, Drama` | Finds movies with any of these genres |
| **Production Countries** | Comma-separated | `United States, France` | Finds movies from any of these countries |
| **Director** | Text search | `Christopher Nolan` | Case-insensitive |
| **Cast** | Text search | `Leonardo DiCaprio` | Case-insensitive |
| **Vote Average** | Minimum value | `7.5` | Returns movies with rating >= value |
| **Release Date** | Date | `2020-01-01` | Exact date match |
| **Runtime** | Minimum minutes | `120` | Returns movies with runtime >= value |
| **IMDb Rating** | Minimum value | `8.0` | Returns movies with rating >= value |
| **Original Language** | Text search | `en` | Case-insensitive |
| **Status** | Text search | `Released` | Case-insensitive |

### How It Works

#### Case-Insensitive Search
All text searches are case-insensitive. Searching for `"action"` will match `"Action"`, `"ACTION"`, `"AcTiOn"`, etc.

#### Comma-Separated Values
When filtering by genres or production countries, you can specify multiple values:
- **Genres**: `Action, Drama, Thriller` - Finds movies with any of these genres
- **Countries**: `United States, United Kingdom` - Finds movies from any of these countries

The script intelligently searches within comma-separated strings stored in the database, so a movie with genres `"Action, Drama, Thriller"` will be found when you search for `"Action"`.

#### SQL Query Generation
The script builds SQL queries using:
- `LIKE` for text searches (with `LOWER()` for case-insensitivity)
- `>=` for minimum value filters (vote_average, runtime, imdb_rating)
- `=` for exact matches (dates, IDs)
- `IN` for multiple value filters
- Custom LIKE patterns for comma-separated string columns

#### Custom SQL Queries
You can bypass the filter interface and write your own SQL query directly. The script will execute it and display results.

### Usage Examples

#### Example 1: Find Action Movies
```
Title: [Enter]
Genres: Action
Director: [Enter]
...
```
Returns all movies with "Action" in their genres list.

#### Example 2: High-Rated Movies from Multiple Countries
```
Genres: [Enter]
Production Countries: United States, France, United Kingdom
Vote Average: 7.5
IMDb Rating: 8.0
...
```
Returns highly-rated movies from any of the specified countries.

#### Example 3: Movies by Director
```
Director: Christopher Nolan
Runtime: 120
...
```
Returns Christopher Nolan movies that are at least 120 minutes long.

#### Example 4: View All Results
When results are displayed, you'll be prompted:
```
How many results to display? (Enter for 10, 'all' for all, or a number): all
```

### Manual Installation (Optional)

If you prefer to install dependencies manually:

```bash
pip install -r requirements.txt
```

Or with user install (for externally-managed Python environments):

```bash
pip install --user mysql-connector-python
```

### Backend Integration

The `MovieDatabase` class can be easily imported and used in Flask/FastAPI endpoints:

```python
from database_query import MovieDatabase

# Initialize
db = MovieDatabase(host, database, user, password, port)
db.connect()

# Query with filters
filters = {
    'genres': ['Action', 'Drama'],
    'vote_average': {'operator': '>=', 'value': 7.5}
}
results = db.query_movies(filters, limit=50)

# Execute custom query
results = db.execute_query("SELECT * FROM movies WHERE genres LIKE %s", ('%Action%',))
```

### Technical Details

- **Database**: MySQL
- **Python Version**: 3.6+
- **Dependencies**: mysql-connector-python
- **Query Method**: Parameterized queries (SQL injection safe)
- **Case Handling**: All string comparisons use MySQL `LOWER()` function
