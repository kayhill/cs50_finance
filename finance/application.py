import os

from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""

    if request.method == "GET":

        rows = db.execute("SELECT symbol, SUM(shares) as total_shares FROM purchases WHERE user_id=:user_id GROUP BY symbol HAVING total_shares > 0", user_id=session["user_id"])

        for row in rows:
            quote = lookup(row['symbol'])
            price = round(quote['price'], 2)
            company = quote['name']
            row.update({'company' : company})
            row.update({'price' : price})
            value = round(price * row['total_shares'], 2)
            row.update({'value' : value})

        cash = db.execute("SELECT cash FROM users WHERE id=:user_id", user_id=session["user_id"])

        return render_template("index.html", cash=round(cash[0]["cash"], 2), rows=rows)

    else:

        loan = request.form.get("loan")

        # Ensure loan amount was sumbitted
        if not request.form.get("loan"):
            return apology("must provide loan amount", 403)

        elif int(loan) > 10000:
            return apology("number must be less than 10000", 403)

        elif int(loan) <= 0:
            return apology("number must be greater than 0", 403)

        else:
            db.execute("UPDATE users SET cash = cash + :loan WHERE id=:user_id", loan = loan, user_id=session["user_id"])


            return redirect("/")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via link or url, display page
    if request.method == "GET":
        return render_template("buy.html")

    # User submits symbol to buy
    elif request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        quote = lookup(symbol)

        # Ensure symbol was sumbitted
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("must provide symbol and number of shares", 403)

        #Verify input
        elif quote == None:
            return apology("symbol does not exist", 403)

        elif int(shares) <= 0:
            return apology("number must be greater than 0", 403)

     # if input valid, calculate cost of purchase
        else:
            cost = quote['price'] * int(shares)

          # Query database for user's cash
            rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

            cash_remaining = rows[0]["cash"]

            # Check if user has enough money
            if cash_remaining < cost:
                return apology("no money honey", 403)

            else:
            # Update cash in user table
                db.execute("UPDATE users SET cash = cash - :price WHERE id = :user_id", price=cost, user_id=session["user_id"])

            #create new table to store purchase history
               # db.execute("CREATE TABLE purchases (user_id NUMERIC NOT NULL, symbol TEXT NOT NULL, price NUMERIC NOT NULL, shares NUMERIC NOT NULL, time NUMERIC NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))")

                now = datetime.now()

            #put info into purchases table
                db.execute("INSERT INTO purchases (user_id, symbol, price, shares, time) VALUES(?, ?, ?, ?, ?)", session["user_id"], symbol, quote['price'], shares, now)

                return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    rows = db.execute("SELECT symbol, price, shares, time FROM purchases WHERE user_id=:user_id ORDER BY time DESC", user_id=session["user_id"])
    for row in rows:
        if row['shares'] > 0:
            transaction = "Bought"
        elif row['shares'] < 0:
            transaction = "Sold"
        row.update({'transaction' : transaction})

    return render_template("history.html", rows=rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via link or url, show form
    if request.method == "GET":
        return render_template("quote.html")

    # User submits acronym
    elif request.method == "POST":

        #Ensure symbol is submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        symbol = request.form.get("symbol")
        quote = lookup(symbol)

        if quote == None:
            return apology("symbol does not exist", 403)

    return render_template("quoted.html", table = quote)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via link or url
    if request.method == "GET":
        return render_template("register.html")

    # User reached route via POST (as by submitting a form via POST)
    elif request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password was confirmed
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 403)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username does not exist
        if len(rows) == 1:
            return apology("username unavailable", 403)

        # Store username and password into table
        db.execute("INSERT INTO users (username, hash) VALUES(?,?)", request.form.get("username"), generate_password_hash(request.form.get("password")))


        # Redirect user to home page
        return redirect("/")





@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # User reached route via link or url, display page
    if request.method == "GET":

        stocks = db.execute("SELECT symbol, SUM(shares) as total_shares FROM purchases WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0 ", user_id=session["user_id"])

        return render_template("sell.html", stocks=stocks)

    # User submits symbol to buy
    elif request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        quote = lookup(symbol)


        # Ensure symbol was sumbitted
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("must provide symbol and number of shares", 403)

        #Verify input
        elif quote == None:
            return apology("symbol does not exist", 403)

        elif int(shares) <= 0:
            return apology("number must be greater than 0", 403)

        # Query database for # shares user owns
        else:
            own = db.execute("SELECT symbol, SUM(shares) as total_shares FROM purchases WHERE user_id=:user_id GROUP BY symbol=:symbol HAVING total_shares > 0", user_id=session["user_id"], symbol=symbol)

            #if user does not own enough shares, return error message
            for row in own:
                  if  int(shares) > row["total_shares"]:
                    return apology("not enough shares for sale")

            value = quote['price'] * int(shares)

            #if all checks passed, update users table
            db.execute("UPDATE users SET cash = cash + :price WHERE id = :user_id", price=value, user_id=session["user_id"])

            sold = 0 - int(shares)
            now = datetime.now()

            #update purchases table
            db.execute("INSERT INTO purchases (user_id, symbol, price, shares, time) VALUES(?, ?, ?, ?, ?)", session["user_id"], symbol, quote['price'], sold, now)

            return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
