from flask import Flask, render_template, request, redirect, session, flash, url_for,jsonify
from flask_mysqldb import MySQL
import bcrypt
from database_query import MovieDatabase, MYSQL_CONFIG


app = Flask(__name__)
app.secret_key = "supersecretkey"

# MySQL Configuration
app.config['MYSQL_HOST'] = ''
app.config['MYSQL_USER'] = ''
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'Recflix'

mysql = MySQL(app)

# Home route
@app.route('/')
def home():
    return redirect('/login')

# Registration Page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())

        cur = mysql.connection.cursor()
        # Check if user exists
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        account = cur.fetchone()
        if account:
            flash("User already exists. Please login.", "danger")
            return redirect('/login')
        
        # Insert new user
        cur.execute("INSERT INTO users (full_name, email, password) VALUES (%s, %s, %s)",
                    (full_name, email, hashed_password))
        mysql.connection.commit()
        cur.close()
        flash("Account created successfully! Please login.", "success")
        return redirect('/login')

    return render_template('register.html')


# Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'].encode('utf-8')

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id, full_name, password FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()

        if not user:
            # Email not registered
            return render_template('login.html', message="Email not registered. Please create an account.")
        
        if bcrypt.checkpw(password, user[2].encode('utf-8')):
            session['user_id'] = user[0]
            session['full_name'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', message="Incorrect password. Please try again.")

    return render_template('login.html')



# Helper function to fetch trending movies from local DB (for new users)
def get_local_trending_movies():
    cur = mysql.connection.cursor()
    # Trending: Recent releases (last 2 years) with high popularity and weighted rating
    query = """
        SELECT id, title, poster_path, popularity, vote_average, vote_count, release_date
        FROM movies
        WHERE release_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
        ORDER BY (vote_average * vote_count / (vote_count + 100)) + popularity DESC
    """
    cur.execute(query)
    results = cur.fetchall()
    cur.close()
    # Return as list of dicts for easy template use
    return [{'id': row[0], 'title': row[1], 'poster_path': row[2], 'popularity': row[3], 'vote_average': row[4], 'vote_count': row[5], 'release_date': row[6]} for row in results]


# Dashboard Page
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect('/login')

    user_name = session['full_name']
    user_id = session['user_id']

    cur = mysql.connection.cursor()
    # Fetch user's watchlist
    cur.execute("SELECT movie_id, title, poster_path FROM watchlist WHERE user_id=%s", (user_id,))
    watchlist = cur.fetchall()
    cur.close()

    is_new_user = len(watchlist) == 0
    trending_movies = get_local_trending_movies()

    # --- Handle search if any ---
    search_query = request.args.get('query', '').strip()
    search_results = []
    if search_query:
        filters = {'title': search_query}
        db = MovieDatabase(
            host=MYSQL_CONFIG['host'],
            database=MYSQL_CONFIG['database'],
            user=MYSQL_CONFIG['user'],
            password=MYSQL_CONFIG['password'],
            port=MYSQL_CONFIG['port']
        )
        if db.connect():
            search_results = db.query_movies(filters)
            db.disconnect()

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT movie_id, title, poster_path 
        FROM already_watched 
        WHERE user_id = %s 
    """, (user_id,))
    already_watched = cur.fetchall()
   

    cur.execute("SELECT movie_id FROM reviews WHERE user_id=%s", (user_id,))
    reviewed_movies = [row[0] for row in cur.fetchall()]

   
    cur.close()

    return render_template(
        'dashboard.html',
        user_name=user_name,
        trending_movies=trending_movies,
        watchlist=watchlist,
        is_new_user=is_new_user,
        search_results=search_results,
        search_query=search_query,
        already_watched=already_watched,
        reviewed_movies=reviewed_movies
    )

#create watch list
@app.route('/add_to_watchlist', methods=['POST'])
def add_to_watchlist():
    if 'user_id' not in session:
        flash("Please log in to add movies to your watchlist.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    movie_id = request.form['movie_id']
    title = request.form['title']
    poster_path = request.form['poster_path']

    cur = mysql.connection.cursor()

    # Check if movie is already in watchlist
    cur.execute("SELECT * FROM watchlist WHERE user_id=%s AND movie_id=%s", (user_id, movie_id))
    existing = cur.fetchone()

    if existing:
        flash("This movie is already in your watchlist!", "info")
    else:
        cur.execute(
            "INSERT INTO watchlist (user_id, movie_id, title, poster_path) VALUES (%s, %s, %s, %s)",
            (user_id, movie_id, title, poster_path)
        )
        mysql.connection.commit()
        flash(f"Added '{title}' to your watchlist!", "success")

    cur.close()
    return redirect(url_for('dashboard'))

#remove from watch list
@app.route('/remove_from_watchlist', methods=['POST'])
def remove_from_watchlist():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    movie_id = request.form['movie_id']

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM watchlist WHERE user_id=%s AND movie_id=%s", (user_id, movie_id))
    mysql.connection.commit()
    cur.close()

    flash("Movie removed from your watchlist.", "info")
    return redirect(url_for('dashboard'))

#already watched
@app.route('/already_watched', methods=['POST'])
def already_watched():
    if 'user_id' not in session:
        flash("Please login to watch movies.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    movie_id = request.form['movie_id']
    title = request.form['title']
    poster_path = request.form['poster_path']

    cur = mysql.connection.cursor()

    # Check if already in already_watched
    cur.execute("SELECT * FROM already_watched WHERE user_id=%s AND movie_id=%s", (user_id, movie_id))
    existing = cur.fetchone()

    if existing:
        # Update last_watched timestamp if movie already exists
        cur.execute(
            "UPDATE already_watched SET last_watched = NOW() WHERE user_id=%s AND movie_id=%s",
            (user_id, movie_id)
        )
    else:
        # Insert new row with last_watched as NULL initially, then update timestamp
        cur.execute(
            "INSERT INTO already_watched (user_id, movie_id, title, poster_path, last_watched) "
            "VALUES (%s, %s, %s, %s, NOW())",
            (user_id, movie_id, title, poster_path)
        )

    mysql.connection.commit()
    cur.close()

    flash(f"Now playing '{title}' — added to Already Watched!", "success")
    return redirect(url_for('dashboard'))

#updating the last_watched details
@app.route('/update_last_watched', methods=['POST'])
def update_last_watched():
    if 'user_id' not in session:
        flash("Login required", "warning")
        return redirect(url_for('dashboard'))

    movie_id = request.form.get('movie_id')  
    user_id = session['user_id']

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE already_watched SET last_watched = NOW() WHERE user_id=%s AND movie_id=%s",
        (user_id, movie_id)
    )
    mysql.connection.commit()
    cur.close()

    flash("Resume time updated!", "success")
    return redirect(url_for('movie_details', movie_id=movie_id))

#fetching movie details based on selected movie 
@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    if 'user_id' not in session:
        flash("Login required", "warning")
        return redirect(url_for('dashboard'))

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    # Join already_watched and movies to get overview as description
    cur.execute("""
        SELECT aw.title, aw.poster_path, aw.last_watched, m.overview
        FROM already_watched aw
        JOIN movies m ON aw.movie_id = m.id
        WHERE aw.user_id=%s AND aw.movie_id=%s
    """, (user_id, movie_id))

    result = cur.fetchone()
    cur.close()

    if not result:
        flash("No details found for this movie.", "warning")
        return redirect(url_for('dashboard'))

    title, poster_path, last_watched, description = result

    return render_template(
        "movieDetails.html",
        movie_id=movie_id,
        title=title,
        poster_path=poster_path,
        last_watched=last_watched,
        description=description
    )

#reviews
@app.route('/add_review', methods=['POST'])
def add_review():
    if 'user_id' not in session:
        flash("Please login to write a review.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    movie_id = request.form['movie_id']
    rating = request.form['rating']
    review_text = request.form['review_text']

    cur = mysql.connection.cursor()

    # Check if review already exists for this user and movie
    cur.execute("SELECT * FROM reviews WHERE user_id=%s AND movie_id=%s", (user_id, movie_id))
    existing_review = cur.fetchone()
    if existing_review:
        flash("You have already submitted a review for this movie.", "info")
        cur.close()
        return redirect(url_for('dashboard'))

    # Insert new review
    cur.execute("""
        INSERT INTO reviews (user_id, movie_id, rating, review_text)
        VALUES (%s, %s, %s, %s)
    """, (user_id, movie_id, rating, review_text))
    mysql.connection.commit()
    cur.close()

    flash("Your review has been submitted!", "success")
    return redirect(url_for('dashboard'))






# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect('/login')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
