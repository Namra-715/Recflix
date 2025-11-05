from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_mysqldb import MySQL
import bcrypt

app = Flask(__name__)
app.secret_key = "supersecretkey"

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Puttumari230&'
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




# Dashboard Page
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect('/login')

    user_name = session['full_name']

    # You can fetch watchlist/recommendations here
    return render_template('dashboard.html', user_name=user_name)


# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect('/login')


if __name__ == '__main__':
    app.run(debug=True)
