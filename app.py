from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_mysqldb import MySQL
import bcrypt

app = Flask(__name__)
app.secret_key = "supersecretkey"

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'your_password'
app.config['MYSQL_DB'] = 'your_db_name'

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

    # Fetch user's watchlist
    cur = mysql.connection.cursor()
    cur.execute("SELECT movie_id, title, poster_path FROM watchlist WHERE user_id=%s", (user_id,))
    watchlist = cur.fetchall()
    cur.close()

    # Determine if user is "new" (empty watchlist)
    is_new_user = len(watchlist) == 0

    trending_movies = []
    if is_new_user:
        # For new users: Use local trending movies
        trending_movies = get_local_trending_movies()
        if not trending_movies:
            # Fallback to TMDB if local fails
            trending_movies = get_trending_movies()
    else:
        # For returning users: Use TMDB trending (or mix with local)
        trending_movies = get_trending_movies()

    return render_template('dashboard.html', 
                           user_name=user_name, 
                           trending_movies=trending_movies, 
                           watchlist=watchlist, 
                           is_new_user=is_new_user)


# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect('/login')


if __name__ == '__main__':
    app.run(debug=True)
