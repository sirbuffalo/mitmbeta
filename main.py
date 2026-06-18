from datetime import datetime, timezone
from os import getenv, makedirs
from secrets import token_urlsafe
from urllib.parse import urlencode

import requests
from flask import Flask, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.secret_key = getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = getenv('DATABASE_URL', 'sqlite:///app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v2/userinfo'
GOOGLE_SCOPES = 'openid email profile'

COURSES = {

    'home':{
        'question' : '',
       'courses' :    [],
        'links' :   []
    },

    'Algebra and Calculus A':
    
    {

        "question" : "How can we find the minimum of a function?",

    'nodes' : [
   {"id":"Minimization"},
   {"id":"Differentiation"},
   {"id":"Solving\nFor 0s"},
   {"id":"Solving\nLinear\nEquations"},
   {"id":"Solving\nQuadratic\nEquations"},
   {"id":"Power\nRule"},
   {"id":"Product\nRule"},
   {"id":"Quotient\nRule"},
   {"id":"Chain\nRule"}
   ],


    'edges' : [
   ["Minimization", "Differentiation"],
   ["Minimization", "Solving\nFor 0s"],
   ["Product\nRule", "Power\nRule"],
   ["Quotient\nRule", "Product\nRule"],
   ["Chain\nRule", "Product\nRule"],
   ["Differentiation", "Chain\nRule"],
   ["Differentiation", "Power\nRule"],
   ["Differentiation", "Quotient\nRule"],
   ["Differentiation", "Product\nRule"],
   ["Solving\nFor 0s", "Solving\nLinear\nEquations"],
   ["Solving\nQuadratic\nEquations", "Solving\nLinear\nEquations"],
   ["Solving\nFor 0s", "Solving\nQuadratic\nEquations"]
    ]
    },

    'Combinatorics': 
    {

    "question": "Suppose we have 13 people in a line randomly jump either left or right. What is the probability that the teams will differ by at least 2 people?",


  "nodes": [
    {"id": "Basic\nArithmetic"},
    {"id": "Factorials"},
    {"id": "Permutations"},
    {"id": "Combinations"},
    {"id": "Choose"},
    {"id": "Overcounting"},
    {"id": "Complementary\nCounting"},
    {"id": "Probability"},
   {"id":"Jumping\nProblem"}
  ],

  "edges": [
    ["Factorials", "Basic\nArithmetic"],

    ["Permutations", "Factorials"],
    ["Combinations", "Factorials"],

    ["Choose", "Combinations"],

    ["Probability", "Basic\nArithmetic"],

    ["Overcounting", "Permutations"],
    ["Overcounting", "Combinations"],

    ["Complementary\nCounting", "Probability"],
   ["Jumping\nProblem", "Complementary\nCounting"],
   ["Jumping\nProblem", "Choose"]
  ]
}

}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=True)
    picture = db.Column(db.String(1024), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


makedirs(app.instance_path, exist_ok=True)
with app.app_context():
    db.create_all()


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/about-us')
def about_us():
    return render_template('aboutus.html')


@app.get('/login')
def login():
    return render_template(
        'login.html',
        user=session.get('user'),
        google_configured=bool(getenv('GOOGLE_CLIENT_ID') and getenv('GOOGLE_CLIENT_SECRET')),
    )


@app.get('/account')
def account():
    user = session.get('user')
    if user is None:
        return redirect(url_for('login'))

    return render_template('account.html', user=user)


@app.get('/login/google')
def google_login():
    client_id = getenv('GOOGLE_CLIENT_ID')
    client_secret = getenv('GOOGLE_CLIENT_SECRET')
    if not client_id or not client_secret:
        return render_template(
            'login.html',
            error='Google sign in is not configured yet.',
            google_configured=False,
            user=session.get('user'),
        ), 500

    state = token_urlsafe(32)
    session['oauth_state'] = state

    auth_params = {
        'client_id': client_id,
        'redirect_uri': url_for('google_callback', _external=True),
        'response_type': 'code',
        'scope': GOOGLE_SCOPES,
        'state': state,
        'prompt': 'select_account',
    }
    return redirect(f'{GOOGLE_AUTH_URL}?{urlencode(auth_params)}')


@app.get('/login/callback')
def google_callback():
    if request.args.get('error'):
        return render_template(
            'login.html',
            error=f'Google sign in failed: {request.args["error"]}',
            google_configured=True,
            user=session.get('user'),
        ), 400

    if request.args.get('state') != session.pop('oauth_state', None):
        return render_template(
            'login.html',
            error='Google sign in failed because the session state did not match.',
            google_configured=True,
            user=session.get('user'),
        ), 400

    code = request.args.get('code')
    if not code:
        return render_template(
            'login.html',
            error='Google did not return an authorization code.',
            google_configured=True,
            user=session.get('user'),
        ), 400

    token_response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            'code': code,
            'client_id': getenv('GOOGLE_CLIENT_ID'),
            'client_secret': getenv('GOOGLE_CLIENT_SECRET'),
            'redirect_uri': url_for('google_callback', _external=True),
            'grant_type': 'authorization_code',
        },
        timeout=10,
    )

    if not token_response.ok:
        return render_template(
            'login.html',
            error='Google sign in failed while exchanging the authorization code.',
            google_configured=True,
            user=session.get('user'),
        ), 400

    access_token = token_response.json().get('access_token')
    userinfo_response = requests.get(
        GOOGLE_USERINFO_URL,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10,
    )

    if not userinfo_response.ok:
        return render_template(
            'login.html',
            error='Google sign in failed while loading your profile.',
            google_configured=True,
            user=session.get('user'),
        ), 400

    google_user = userinfo_response.json()
    user = User.query.filter_by(google_id=google_user.get('id')).first()

    if user is None:
        user = User(google_id=google_user.get('id'), email=google_user.get('email'))
        db.session.add(user)

    user.email = google_user.get('email')
    user.name = google_user.get('name')
    user.picture = google_user.get('picture')
    db.session.commit()

    session['user'] = {
        'id': user.id,
        'google_id': user.google_id,
        'email': user.email,
        'name': user.name,
        'picture': user.picture,
    }
    return redirect(url_for('account'))


@app.post('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.get('/courses/<course>')
def courses(course):


    user = session.get('user')
    if user is None:
        return redirect(url_for('login'))

    if course != 'home':
        return render_template('course1.html', user=session.get('user'), course_name = course, courses = COURSES[course])
    else:
        return render_template('courses.html', user=session.get('user'))




if __name__ == '__main__':
    app.run(debug=True, port=8000)
