from flask import Flask, render_template


app = Flask(__name__)

@app.get('/')
def home():
    return render_template('index.html')

@app.get('/about-us')
def about_us():
    return render_template('aboutus.html')

if __name__ == '__main__':
    app.run(debug=True, port=8000)
