import os
import requests
import csv

from flask import Flask, session, render_template, redirect, request, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

# file = open("books.csv")
# reader = csv.reader(file)

# for isbn, title, author, year in reader:
#     db.execute("INSERT INTO books(isbn, title, author, year) VALUES (:isbn, :title, :author, :year)", {"isbn": isbn, "title": title, "author": author, "year": year})
#     print(f"Added {isbn}, {title}, {author}, {year}")
# db.commit()
   


@app.route("/")
def index():
    if session.get("authentication") == True:
        books = db.execute("SELECT * FROM books LIMIT 20")
    else:
        session["authentication"] = False
        return render_template("index.html", authentication = False)
    return render_template("index.html", data = books, authentication = True)
    

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    else:
        email = request.form.get("email")
        password = request.form.get("password")

        user = db.execute("SELECT * FROM users WHERE email= :email AND password= :password", {"email": email, "password": password}).rowcount
        usedid = db.execute("SELECT id FROM users WHERE email= :email AND password= :password", {"email": email, "password": password}).fetchone()

        if user == 0:
            session["authentication"] = False
            return render_template("login.html", error = "Wrong email or password")
        else:
            session["authentication"] = True
            session["userid"] = usedid

            return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        return render_template("register.html")
    else:
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

    if name == "" or email == "" or password == "":
        return render_template("register.html", error = "Fill in the form")
    elif db.execute("SELECT email FROM users WHERE email= :email", {"email": email}).rowcount == 0:
        db.execute("INSERT INTO users(name, email, password) VALUES (:name, :email, :password)", {"name": name, "email": email, "password": password})
        db.commit()

        if db.execute("SELECT email FROM users WHERE email= :email", {"email": email}).rowcount == 0:
            return render_template("error.html", message = "User not registered, try again please")
        else:
            return redirect("/login")
    else:
        return render_template("register.html", error = "User exist, try another email")

@app.route("/logout")
def logout():
    if session.get("authentication") == True:
        session["authentication"] = False
    else:
        pass
    return redirect("/")

@app.route("/search", methods=["POST"])
def search():

    if session.get("authentication") == False:
        return redirect("/login")
    elif session.get("authentication") == True:
        querry = request.form.get("search")
        querry = "%" + querry + "%"
        if db.execute("SELECT * FROM books WHERE title LIKE :querry OR author LIKE :querry OR year LIKE :querry OR isbn LIKE :querry", {"querry": querry}).rowcount == 0:
            return render_template("index.html", error = "Not found")
        else:
           data = db.execute("SELECT * FROM books WHERE title LIKE :querry OR author LIKE :querry OR year LIKE :querry OR isbn LIKE :querry", {"querry": querry}).fetchall()
        
        return render_template("index.html", data = data)

@app.route("/book/<string:bookid>")
def book(bookid):
    if session.get("authentication") == False:
        return redirect("/login")
    elif db.execute("SELECT id from books WHERE id= :bookid", {"bookid": bookid}).rowcount == 0:
        return render_template("error.html", message = "Book not found!")
    else:
        bookdata = db.execute("SELECT * FROM books WHERE id= :id", {"id": bookid}).fetchone()
        reviewdata = db.execute("SELECT * FROM reviews WHERE book_id= :id", {"id": bookid}).fetchall()

        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "hXu77BZqWpM8URNXI4dpQQ", "isbns": bookdata.isbn})
        data = res.json()

    return render_template("book.html", book = bookdata, review = reviewdata, goodreads_data = data, authentication = True)


@app.route("/review/<string:bookid>", methods=["POST"])
def review(bookid):
    if session.get("authentication") == False:
        return redirect("/login")
    else:
        rate = request.form.get("rate")
        note = request.form.get("review_note")
        userid = session.get("userid")[0]

        if db.execute("SELECT user_id FROM reviews WHERE user_id= :userid AND book_id= :bookid", {"userid": userid, "bookid": bookid}).rowcount == 0:
            db.execute("INSERT INTO reviews (rating, review, user_id, book_id) VALUES (:rate, :note, :userid, :bookid)", {"rate": rate, "note": note, "userid": userid, "bookid": bookid})
            db.commit()
        else:
            return render_template("error.html", message = "You can only submit a review once, Sorry!", authentication = True)

        return redirect(f"/book/{bookid}")


@app.route("/api/<string:isbn>")
def bookroute(isbn):
    if db.execute("SELECT isbn FROM books WHERE isbn= :isbn", {"isbn": isbn}).rowcount == 0:
        return jsonify ({
            "isbn": isbn,
            "message": "ISBN not found"
        })
    else:
        book = db.execute("SELECT * FROM books WHERE isbn= :isbn", {"isbn": isbn}).fetchone()
        rating = db.execute("SELECT AVG(rating) FROM reviews WHERE book_id= :bookid", {"bookid": book.id}).fetchone()
        count = db.execute("SELECT COUNT(*) FROM reviews WHERE book_id= :bookid", {"bookid": book.id}).fetchone()

        return jsonify ({
            "title": book.title,
            "author": book.author,
            "year": book.year,
            "isbn": book.isbn,
            "review_count": count[0],
            "average_score": float(rating[0])
        })

@app.route("/me")
def me():
    return "Hello"