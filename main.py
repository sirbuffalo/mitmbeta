from flask import Flask, render_template

# Create the application instance
app = Flask(__name__)

# Route for the Home page (Returns text)
@app.route('/')
def home():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True, port=8000)
