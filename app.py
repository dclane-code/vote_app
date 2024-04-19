from flask import Flask, g, render_template, request, redirect, url_for, session, flash
import sqlite3
import secrets

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
app.config['DATABASE'] = 'votes.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    if 'user_id' in session:
        user_id = session['user_id']
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT player, points FROM votes WHERE user_id=?", (user_id,))
        voted_players = cursor.fetchall()
        cursor.execute("SELECT name FROM players")
        available_players = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return render_template('index.html', available_players=available_players, voted_players=voted_players)
    else:
        return redirect(url_for('login'))

@app.route('/admin/voting_codes')
def admin_voting_codes():
    if 'username' in session and session['username'] == 'admin':
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id, username, voting_code FROM users")
        users = cursor.fetchall()
        cursor.close()
        return render_template('admin_voting_codes.html', users=users)
    else:
        return redirect(url_for('login'))

@app.route('/admin/reset_voting_code/<int:user_id>', methods=['POST'])
def reset_voting_code(user_id):
    if 'username' in session and session['username'] == 'admin':
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE users SET voting_code = 'password' WHERE id = ?", (user_id,))
        db.commit()
        cursor.close()
        flash('Voting code reset successfully', 'success')
    return redirect(url_for('admin_voting_codes'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        selected_username = request.form['username']
        voting_code = request.form['voting_code']
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id, username, voting_code FROM users WHERE username = ?", (selected_username,))
        user = cursor.fetchone()
        cursor.close()

        if user and user[2] == voting_code:
            session.clear()
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('index'))
        else:
            flash('Incorrect username or voting code', 'error')
            return redirect(url_for('login'))

    # Retrieve list of usernames from the database
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT username FROM users")
    usernames = [row[0] for row in cursor.fetchall()]
    cursor.close()

    return render_template('login.html', usernames=usernames)


@app.route('/admin/reset_votes', methods=['POST'])
def reset_votes():
    if 'user_id' in session and session['username'] == 'admin':
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM votes")
        db.commit()
        cursor.close()
        flash('All votes have been reset', 'success')
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/vote', methods=['POST'])
def vote():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    # Check if the user has already voted
    cursor.execute("SELECT COUNT(*) FROM votes WHERE user_id=?", (user_id,))
    vote_count = cursor.fetchone()[0]
    if vote_count > 0:
        cursor.close()
        return "You have already voted. You cannot vote again."

    try:
        # Process the new votes
        for i in range(1, 4):
            player = request.form.get(f'player{i}')
            points = request.form.get(f'points{i}')
            cursor.execute("INSERT INTO votes (user_id, player, points) VALUES (?, ?, ?)", (user_id, player, points))
        
        # Commit changes to the database
        db.commit()
    except Exception as e:
        # Rollback changes if an error occurs
        db.rollback()
        print("Error:", e)
        return "An error occurred while processing your vote."

    finally:
        cursor.close()

    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    if 'user_id' in session and session['username'] == 'admin':
        return render_template('admin.html')
    else:
        return redirect(url_for('login'))

@app.route('/admin/results')
def results():
    if 'user_id' in session and session['username'] == 'admin':
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT player, SUM(points) FROM votes GROUP BY player ORDER BY SUM(points) desc")
        vote_results = cursor.fetchall()
        cursor.close()
        return render_template('results.html', vote_results=vote_results)
    else:
        return redirect(url_for('login'))

@app.route('/admin/add_user', methods=['GET', 'POST'])
def add_user():
    if 'user_id' in session and session['username'] == 'admin':
        if request.method == 'POST':
            username = request.form['username']
            voting_code = request.form['voting_code']
            db = get_db()
            cursor = db.cursor()
            cursor.execute("INSERT INTO users (username, voting_code) VALUES (?, ?)", (username, voting_code))
            db.commit()
            cursor.close()
            return redirect(url_for('admin'))
        else:
            return render_template('add_user.html')
    else:
        return redirect(url_for('login'))

@app.route('/admin/remove_user', methods=['GET', 'POST'])
def remove_user():
    if 'user_id' in session and session['username'] == 'admin':
        if request.method == 'POST':
            user_id = request.form['user_id']
            db = get_db()
            cursor = db.cursor()
            cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
            db.commit()
            cursor.close()
            return redirect(url_for('admin'))
        else:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT id, username FROM users")
            users = cursor.fetchall()
            cursor.close()
            return render_template('remove_user.html', users=users)
    else:
        return redirect(url_for('login'))

@app.route('/admin/add_player', methods=['GET', 'POST'])
def add_player():
    if 'user_id' in session and session['username'] == 'admin':
        if request.method == 'POST':
            name = request.form['name']
            db = get_db()
            cursor = db.cursor()
            cursor.execute("INSERT INTO players (name) VALUES (?)", (name,))
            db.commit()
            cursor.close()
            return redirect(url_for('admin'))
        else:
            return render_template('add_player.html')
    else:
        return redirect(url_for('login'))

@app.route('/admin/remove_player', methods=['GET', 'POST'])
def remove_player():
    if 'user_id' in session and session['username'] == 'admin':
        if request.method == 'POST':
            player_id = request.form['player_id']
            db = get_db()
            cursor = db.cursor()
            cursor.execute("DELETE FROM players WHERE id=?", (player_id,))
            db.commit()
            cursor.close()
            return redirect(url_for('admin'))
        else:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT id, name FROM players")
            players = cursor.fetchall()
            cursor.close()
            return render_template('remove_player.html', players=players)
    else:
        return redirect(url_for('login'))

@app.route('/admin/voted_users')
def voted_users():
    if 'user_id' in session and session['username'] == 'admin':
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT DISTINCT username FROM users INNER JOIN votes ON users.id = votes.user_id")
        voted_users = cursor.fetchall()
        cursor.close()
        return render_template('voted_users.html', voted_users=voted_users)
    else:
        return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port='80', debug=True)

