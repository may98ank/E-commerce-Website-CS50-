from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    row = db.execute("SELECT sym FROM uc_connect where id = :id", id = session["user_id"])
    bls = []
    cash = 0
    for each in row:
        ls = []
        shares = db.execute("select sum(shares) AS srs from ud where uid = :id and symbol = :sym", id = session["user_id"], sym = each["sym"])
        if int(shares[0]["srs"]) == 0:
            continue
        info = lookup(each["sym"])
        while info == None:
            info = lookup(each["sym"])
        ls.append(str(info["symbol"]))
        name = info["name"]
        ls.append(name)
        price = info["price"]
        total = price*int(shares[0]["srs"])
        cash += total
        ls.append(shares[0]["srs"])
        ls.append(usd(price))
        ls.append(usd(total))
        bls.append(ls)
    row = db.execute("SELECT cash from users where id = :id", id = session["user_id"])
    cash += row[0]["cash"]
    return render_template("index.html", bls = bls, var1 = usd(row[0]["cash"]), var2 = usd(cash))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("Incomplete Info Submitted")
        sym = request.form.get("symbol").strip()
        shares = request.form.get("shares")
        if not IsInt(shares):
            return apology("Only +ve Integer Value Of shares");
        quote = lookup(sym)
        if not quote:
            return apology("INVALID SYMBOL")
        price = float(quote["price"])*float(shares)
        id = session["user_id"]
        row = db.execute("SELECT * from users where id = :id", id = id)
        cash = row[0]["cash"]
        # print(cash)
        if cash < price:
            return apology("NOT Enough Cash")
        cash = cash - price
        # print(f"cash : {cash}, price : {price}, shares: {shares} ")
        row = db.execute("select * from uc_connect where id = :id and sym = :sym", id = id, sym = sym)
        if len(row) == 0:
            db.execute("insert into uc_connect values(:id, :sym)", id = id, sym = sym)
        db.execute("UPDATE users SET cash = :cash where id = :id", cash = cash, id = id)
        db.execute("insert into ud (uid, symbol, c_name, price, shares) values( :id, :sym, :name, :price, :shares)",
                    id = id, sym = sym, name = quote["name"], price = quote["price"], shares = shares)
        flash("BOUGHT!")
        return redirect(url_for("index"))
    else:
        return render_template("buy.html")
@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    bls = []
    row = db.execute("select * from ud where uid = :id order by date DESC, time DESC", id = session["user_id"])
    for each in row:
        ls = []
        ls.append(each["symbol"])
        ls.append(each["shares"])
        ls.append(each["price"])
        ls.append(f"{each['date']} {each['time']}")
        bls.append(ls)
    return render_template("history.html", bls = bls)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Symbol nhi Diya")
        sym = request.form.get("symbol")
        quote = lookup(sym)
        if not quote:
            return apology("Abe Galat Symbol Diya hai")
        quote["price"] = usd(quote["price"])
        return render_template("quote.html", q = quote)

    else:
        return render_template("get_quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    if request.method == "POST":
        if not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
            return apology("Details To Dhang Me De BC.....")
        name = request.form.get("username")
        password = request.form.get("password")
        chkpass = request.form.get("confirmation")
        if not password == chkpass:
            return apology("Doosra PassWord Dekh Ke daal le...BC")
        row = db.execute("select username from users where username = :uname", uname = name)
        if len(row) == 0:
            db.execute("insert into users (username, hash) values (:name, :hash)", name = name, hash = pwd_context.hash(password))
            row = db.execute("select * from users where username = :uname", uname = name)
            session["user_id"] = row[0]["id"]
            return redirect(url_for("index"))
        else:
            return apology("Pehle Se Exist Krta Hai")
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("Incomplete Info")
        sym = request.form.get("symbol")
        shares = request.form.get("shares")
        quote = lookup(sym)
        while not quote:
            quote = lookup(sym)
        avil = db.execute("select sum(shares) AS srs from ud where uid = :id and symbol = :sym", id = session["user_id"], sym = quote["symbol"])
        if int(shares) > avil[0]["srs"]:
            return apology("NOT HAVE ENOUGH SHARES")
        price = float(quote["price"])*float(shares)
        id = session["user_id"]
        row = db.execute("SELECT * from users where id = :id", id = id)
        cash = row[0]["cash"]
        cash += price
        db.execute("UPDATE users SET cash = :cash where id = :id", cash = cash, id = id)
        db.execute("insert into ud (uid, symbol, c_name, price, shares) values( :id, :sym, :name, :price, :shares)",
                    id = id, sym = sym, name = quote["name"], price = quote["price"], shares = -1*int(shares))
        flash("SOLD!")
        return redirect(url_for("index"))
    else:
        row = db.execute("select sym from uc_connect where id = :id", id = session["user_id"])
        ls = []
        for each in row:
            shares = db.execute("select sum(shares) AS srs from ud where uid = :id and symbol = :sym", id = session["user_id"], sym = each["sym"])
            if int(shares[0]["srs"]) == 0:
                continue
            ls.append(each["sym"])
        # print(ls)
        return render_template("sell.html", ls = ls)