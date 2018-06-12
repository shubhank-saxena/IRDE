import os
from flask import Flask, request, render_template, flash, redirect, url_for, session, send_file
from flask_mysqldb import MySQL
from passlib.hash import sha256_crypt as sha
from flask_session import Session
from tempfile import mkdtemp
from functools import wraps
import csv


app = Flask(__name__, static_url_path="", static_folder="static")

app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'amwneb1928'
app.config['MYSQL_DB'] = 'IRDE'
app.config['MYSQL_HOST'] = 'localhost'
mysql=MySQL(app)

app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

def execute_db(query,args=()):
    cur=mysql.connection.cursor()
    cur.execute(query,args)
    mysql.connection.commit()
    cur.close()
def query_db(query,args=(),one=False):
    cur=mysql.connection.cursor()
    result=cur.execute(query,args)
    if result>0:
        values=cur.fetchall()
        return values

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['POST','GET'])
def login():
    session.clear()
    if request.method== 'GET':
        return render_template('login.html')
    else:
        id=request.form['id']
        password=request.form['password']
        phash = query_db("select password from member where id = %s", (id, ))
        if phash is None:
            flash("User does not exist","danger")
            return render_template("login.html")

        if sha.verify(password, phash[0][0]):
            session["user_id"] = id
            flash("Login Successful", "success")
            return redirect(url_for("mycart"))
        else:
            flash("Incorrect Password","danger")
            return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route('/signup',methods=['POST','GET'])
def signup():
    if request.method== 'GET':
        return render_template('signup.html')
    else:
        name=request.form['name']
        id=request.form['id']
        password=request.form['password']
        confpassword=request.form['confpassword']
        if password!=confpassword:
            flash("Passwords don't match","danger")

        if query_db("select * from member where id = %s", (id,)) is not None:
            flash("User already taken","danger")
            return render_template("signup.html")

        password=sha.encrypt(password)
        execute_db('insert into member(name,id,password) values(%s,%s,%s)',(
            name,
            id,
            password,
            ))
        return redirect(url_for("login"))

@app.route("/change", methods=["GET", "POST"])
@login_required
def change():
    if request.method == "POST":

        # query database for user
        rows = query_db("SELECT password FROM mentor WHERE email = %s",(session["user_id"],))

        # ensure old password is correct
        if not sha.verify(request.form.get("oldpassword"), rows[0][0]):
            flash('Incorrect old password', 'danger')
            return render_template("change.html")

        # check password match
        if request.form.get("confpassword") != request.form.get("newpassword"):
            flash("Passwords don't match", 'danger')
            return render_template("change.html")

        # another check
        if sha.verify(request.form.get("newpassword"), rows[0][0]):
            flash("New password can't be same as old password", 'danger')
            return render_template("change.html")

        # password encryption
        phash = sha.encrypt(request.form.get("confpassword"))

        execute_db("UPDATE mentor SET password = %s WHERE email = %s",(phash, session["user_id"],))
        flash("Password successfully changed", 'success')
        return redirect(url_for("mygroups"))

    else:
        return render_template("change.html", user=session["user_id"])


@app.route('/', methods=["GET","POST"])
@login_required
def mycart():
    items = query_db("select no, quantity from cart where id = %s",(session["user_id"],))
    cart = []
    if items is not None:
        for item in items:
            temp = query_db("select * from warehouse where no = %s", (item[0],))
            cart.extend(temp)  
    print(len(cart))
    print(items)
    if request.method=="GET":
        return render_template("mycart.html", user=session["user_id"], items=items,cart=cart)
    else:
        for item in items:
            execute_db("delete from cart where id= %s and no=%s ",(session["user_id"],item[0],))
            execute_db("insert into sold values( %s ,%s,%s) ",(session["user_id"],item[0],item[1]))
        
        return render_template("mycart.html",items=None, user=session["user_id"],)

@app.route('/searchitem', methods=["GET","POST"])
@login_required
def searchitem():
    if request.method== 'GET':
        return render_template('searchitem.html', user=session["user_id"])
    else:
        no = request.form['no']
        item = query_db("select * from warehouse where no = %s", (no,))
        print(item)
        if item is None:
            flash("Item not Found", "warning")
        return render_template('searchitem.html',no=no,items=item, user=session["user_id"])
@app.route('/searchstudent', methods=["GET","POST"])
@login_required
def searchstudent():
    if request.method== 'GET':
        return render_template('searchstudent.html', user=session["user_id"], mentor_id=session["mentor_id"])
    else:
        rollno = request.form['rollno']
        students = query_db("select * from student where rollno = %s",(rollno,))
        mentorname = ""
        if students is not None:
            mentor = query_db("select mentor from grp where groupid = %s", (students[0][0],))
            mentorname = query_db("select name from mentor where id = %s", (mentor[0][0],))
        else:
            flash("Student Not Found", "warning")
        return render_template("searchstudent.html",student=students, mentorname=mentorname, user=session["user_id"],mentor_id=session["mentor_id"])



@app.route('/download')
@login_required
def download():
    p=query_db("select * from warehouse")
    with open('static/capstone.csv', 'w') as csvfile:
        fieldnames = ['Item No.', 'Description', 'Quantity', 'Rate', 'Amount']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for a in p:
            writer.writerow({'Item No.' : a[0], 'Description' : a[1], 'Quantity' : a[2], 'Rate': a[3], 'Amount' : a[2]*a[3]})
    return send_file('static/capstone.csv',mimetype='text/csv',attachment_filename='capstone.csv',as_attachment=True)

if __name__ == "__main__":
    app.secret_key = os.urandom(12)
    app.run(host='0.0.0.0',debug=True, port =8080)
