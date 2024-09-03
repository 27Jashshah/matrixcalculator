from flask import Flask,render_template,request,redirect, url_for, session
import random
from flask_sqlalchemy import SQLAlchemy
import datetime
from datetime import date
from flask_login import current_user, login_user, login_required, logout_user, LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from email.message import EmailMessage
import ssl
import smtplib
import os
from dotenv import find_dotenv, load_dotenv
from sqlalchemy.dialects.postgresql import UUID
import uuid


dotenv_path = find_dotenv()
load_dotenv(dotenv_path)


SECRET_KEY = os.getenv("SECRET_KEY")

ADMIN_KEY = os.getenv("ADMIN_KEY")

API_KEY = os.getenv("API_KEY")

SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")

app = Flask(__name__) 

db = SQLAlchemy()

app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SECRET_KEY'] = SECRET_KEY

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(userID):
    return User.query.get(userID)

class User(db.Model, UserMixin):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(200),nullable=False,unique = True)
    emailID = db.Column(db.String(200),nullable=False)
    password = db.Column(db.String(200),nullable=False)
    role = db.Column(db.String(50),nullable=False)
    records = db.relationship('Record', backref='user')

    def __repr__(self):
          return '<user %r>' % self.id


class Record(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    matrix1 = db.Column(db.String(100),nullable=False)
    matrix2 = db.Column(db.String(100),nullable=False)
    operation = db.Column(db.String(100),nullable=False)
    date_created = db.Column(db.Date,default=date.today())
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('user.id'),nullable=False,default=uuid.uuid4)

    def __repr__(self):
          return '<record %r>' % self.id
    
with app.app_context():
    db.create_all()


@app.route('/users')
@login_required
def users():
    if current_user.role == 'admin':
        return render_template('users.html',users = User.query.all())
    else:
        return redirect('/logout')
    

@app.route('/deleteuser/<int:id>')
def deleteUser(id):
    user = User.query.get_or_404(id)

    try:
        db.session.delete(user)
        db.session.commit()
        return redirect('/users')
    except:
        return 'There was an error deleting the User'


@app.route('/records')
@login_required
def records():
    if current_user.role == 'admin':
        return render_template('records.html',records = Record.query.all())
    else:
        return redirect('/logout')


@app.route('/deleterecord/<int:id>')
def deleteRecord(id):
    record = Record.query.get_or_404(id)

    try:
        db.session.delete(record)
        db.session.commit()
        return redirect('/records')
    except:
        return 'There was an error deleting the record'

@app.route('/')
def index():
    if 'user' in session:
        return redirect('/homepage')
    else:
        if 'forgotUser' in session:
            session.pop('forgotUser', None)
        if 'otp' in session:
            session.pop('otp', None)
        return render_template('index.html',incorrectLogin = False, wrongUser = False)


@app.route('/signup',methods=['GET','POST'])
def signUp():
    if request.method == 'POST':
        newUser = User()
        newUser.username = request.form['username']
        newUser.emailID = request.form['email']
        pw = request.form['password1']
        pw2 = request.form['password2']
        if(bool(User.query.filter_by(username=newUser.username).first())):
                return render_template('signUp.html',usedUser = True, passMismatch = False)
        else:
            if pw == pw2:
                newUser.password = generate_password_hash(pw)
                if pw == ADMIN_KEY: 
                    newUser.role = 'admin'
                else:
                    newUser.role = 'client'  
                try:
                    db.session.add(newUser)
                    db.session.commit()
                except:
                    return 'There was an error signing up'
                login_user(newUser)
                session['user'] = newUser.username
                return redirect('/homepage')
            else:
                return render_template('signUp.html',usedUser = False, passMismatch = True)
    else:
        redirect('/gotoSignUp')


@app.route('/gotoSignUp')
def gotoSignUp():
    if 'user' in session:
        return redirect('/homepage')
    else:
        return render_template('signUp.html',usedUser = False, passMismatch = False)


@app.route('/login',methods=['GET','POST'])
def login():
    if request.method == 'POST':
        usern = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username = usern).first()
        if user:
            if check_password_hash(user.password,password):
                login_user(user)
                session['user'] = user.username
                return redirect('/homepage')
            return render_template('login.html',incorrectLogin = True, wrongUser = False)
        
        return render_template('login.html',incorrectLogin = True, wrongUser = True)
    else:
        return redirect('/backlogin')

@app.route('/forgotPassword')
def forgotPassword():
    return render_template('forgotPassword.html',wrongUser = False)

@app.route('/backlogin')
def backlogin():
    if 'user' in session:
        return redirect('/homepage')
    else:
        if 'forgotUser' in session:
            session.pop('forgotUser', None)
        if 'otp' in session:
            session.pop('otp', None)
        return render_template('login.html',incorrectLogin = False, wrongUser = False)

@app.route('/sendotp',methods=['GET','POST'])
def sendotp():
    if request.method == 'POST':
        usern = request.form['username']
        user = User.query.filter_by(username = usern).first()
        if user:
            if ('otp' not in session) or (session['forgotUser'] != user.username):
                email_sender = 'otp.matrix@gmail.com'
                email_password = API_KEY
                email_receiver = user.emailID
                otp = random.randint(100000,999999)

                subject = 'OTP to reset MatrixCalculator password'
                body = """
Hi """ + user.username + """,

We heard that you lost your MatrixCalculator password. Sorry about that!
But don't worry! You can use the following One Time Password (OTP) to reset your password:

""" + str(otp) + """

Thanks,
The MatrixCalculator Team 
"""

                em = EmailMessage()
                em['From'] = email_sender
                em['To'] = email_receiver
                em['Subject'] = subject
                em.set_content(body)
            
                context = ssl.create_default_context()

                with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
                    smtp.login(email_sender,email_password)
                    smtp.sendmail(email_sender,email_receiver, em.as_string())
                
                session['otp'] = otp
            
            session['forgotUser'] = user.username
            return render_template('checkotp.html', wrongotp = False) 
        else:
            return render_template('forgotPassword.html',wrongUser = True)
    else:
        return redirect('/backlogin')

@app.route('/checkingOTP',methods=['GET','POST'])
def checkingOTP():
    if request.method == 'POST':
        otp1 = eval(request.form['otp1']) * 100000
        otp2 = eval(request.form['otp2']) * 10000
        otp3 = eval(request.form['otp3']) * 1000
        otp4 = eval(request.form['otp4']) * 100
        otp5 = eval(request.form['otp5']) * 10
        otp6 = eval(request.form['otp6'])
        otp = otp1 + otp2 + otp3 + otp4 + otp5 + otp6
        if otp == session['otp']:
            return render_template('resetPass.html',passMismatch=False)
        else:
            return render_template('checkotp.html', wrongotp = True) 
    else:
        return redirect('/backlogin')

@app.route('/resettingPass',methods=['GET','POST'])
def resettingPass():
    if request.method == 'POST':
        pw = request.form['password1']
        pw2 = request.form['password2']
        user = User.query.filter_by(username = session['forgotUser']).first()
        if pw == pw2:
            user.password = generate_password_hash(pw) 
            try:
                db.session.commit()
            except:
                return 'There was an error changing the password'
            login_user(user)
            if 'otp' in session:
                session.pop('otp', None)
            if 'forgotUser' in session:
                session.pop('forgotUser', None)
            session['user'] = user.username
            return redirect('/homepage')
        else:
            return render_template('resetPass.html',passMismatch=True)
    else:
        return redirect('/backlogin')

@app.route('/logout',methods=['GET','POST'])
@login_required
def logout():
    logout_user()
    if 'user' in session:
        session.pop('user', None)
    return redirect('/backlogin')



@app.route('/homepage',methods=['GET','POST'])
@login_required
def homepage():
    finalRecs = []
    if request.method == 'POST':
        ops = request.form['operation']
        date = request.form['date']
        whileList = set('abcdefghijkmlnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        ops = ''.join(filter(whileList.__contains__,ops))
        if ops == "" and date != "":
            date = datetime.date.fromisoformat(date)
            records = Record.query.order_by(Record.date_created).filter_by(user_id = current_user.id).filter_by(date_created = date)
            if (records.count() > 0):
                for rec in records:
                    recDict = {
                            'id' : rec.id,
                            'matrix1' : eval(rec.matrix1),
                            'operation' : rec.operation,
                            'date_created' : rec.date_created
                    }
                    if rec.matrix2 == '' or rec.operation == 'Multiply with Scalar':
                        recDict.update({'matrix2' : rec.matrix2})
                    else:  
                        recDict.update({'matrix2' : eval(rec.matrix2)})
                    finalRecs.append(recDict)
            
            return render_template('homepage.html',records=finalRecs, count = records.count(), filOp = False, filDt = True, date = date, op = ops)
        elif date == "" and ops != "":
            records = Record.query.order_by(Record.date_created).filter_by(user_id = current_user.id)
            opsSplit = ops.split()
            for i in range(len(opsSplit)):
                opsSplit[i] = opsSplit[i].capitalize()
            filtRecs = []
            filtRecsCount = 0
            for record in records:
                for op in opsSplit:
                    if op in record.operation:
                        filtRecs.append(record)
                        filtRecsCount = filtRecsCount + 1

            if (filtRecsCount > 0):
                for rec in filtRecs:
                    recDict = {
                            'id' : rec.id,
                            'matrix1' : eval(rec.matrix1),
                            'operation' : rec.operation,
                            'date_created' : rec.date_created
                    }
                    if rec.matrix2 == '' or rec.operation == 'Multiply with Scalar':
                        recDict.update({'matrix2' : rec.matrix2})
                    else:  
                        recDict.update({'matrix2' : eval(rec.matrix2)})
                    finalRecs.append(recDict)

            return render_template('homepage.html',records=finalRecs, count = filtRecsCount, filOp = True, filDt = False, date = date, op = ops)
        elif date != "" and ops != "":
            date = datetime.date.fromisoformat(date)
            records = Record.query.order_by(Record.date_created).filter_by(user_id = current_user.id).filter_by(date_created = date)
            opsSplit = ops.split()
            for i in range(len(opsSplit)):
                opsSplit[i] = opsSplit[i].capitalize()
            filtRecs = []
            filtRecsCount = 0
            for record in records:
                for op in opsSplit:
                    if op in record.operation:
                        filtRecs.append(record)
                        filtRecsCount = filtRecsCount + 1
            
            if (filtRecsCount > 0):
                for rec in filtRecs:
                    recDict = {
                            'id' : rec.id,
                            'matrix1' : eval(rec.matrix1),
                            'operation' : rec.operation,
                            'date_created' : rec.date_created
                    }
                    if rec.matrix2 == '' or rec.operation == 'Multiply with Scalar':
                        recDict.update({'matrix2' : rec.matrix2})
                    else:  
                        recDict.update({'matrix2' : eval(rec.matrix2)})
                    finalRecs.append(recDict)

            return render_template('homepage.html',records=finalRecs, count = filtRecsCount, filOp = True, filDt = True, date = date, op = ops)
        else:
            records = Record.query.order_by(Record.date_created).filter_by(user_id = current_user.id)
            if (records.count() > 0):
                for rec in records:
                    recDict = {
                            'id' : rec.id,
                            'matrix1' : eval(rec.matrix1),
                            'operation' : rec.operation,
                            'date_created' : rec.date_created
                    }
                    if rec.matrix2 == '' or rec.operation == 'Multiply with Scalar':
                        recDict.update({'matrix2' : rec.matrix2})
                    else:  
                        recDict.update({'matrix2' : eval(rec.matrix2)})
                    finalRecs.append(recDict)
            return render_template('homepage.html',records=finalRecs, count = records.count(), filOp = False, filDt = False, date = date, op = ops)
    else:
        records = Record.query.order_by(Record.date_created).filter_by(user_id = current_user.id)
        if (records.count() > 0):
            for rec in records:
                recDict = {
                        'id' : rec.id,
                        'matrix1' : eval(rec.matrix1),
                        'operation' : rec.operation,
                        'date_created' : rec.date_created
                }
                if rec.matrix2 == '' or rec.operation == 'Multiply with Scalar':
                    recDict.update({'matrix2' : rec.matrix2})
                else:  
                    recDict.update({'matrix2' : eval(rec.matrix2)})
                finalRecs.append(recDict)

        return render_template('homepage.html',records=finalRecs, count = records.count(), filOp = False, filDt = False, date = None, op = None)


@app.route('/addition',methods=['GET','POST'])
@login_required
def addition():
    matrix1 = []
    matrix2 = []
    working =[]
    result = []
    if request.method == 'POST':
        for r in range(1,4):
            row1 = []
            row2 = []
            workingrow = []
            resultrow = []
            for c in range(1,4):
                num1 = request.form['M'+str(c)+str(r)]
                num2 = request.form['N'+str(c)+str(r)]
                if num1 != '':
                    row1.append(int(num1))
                else:
                    row1.append(0)
                if num2 != '':
                    row2.append(int(num2))
                else:
                    row2.append(0)
                workingrow.append(str(row1[c-1]) + " + " + str(row2[c-1]))
                resultrow.append(row1[c-1]+row2[c-1])
            matrix1.append(row1)
            matrix2.append(row2)
            working.append(workingrow)
            result.append(resultrow)

        record = Record(matrix1=str(matrix1),matrix2=str(matrix2),operation="Addition",user_id = current_user.id)

        try:
            db.session.add(record)
            db.session.commit()
        except:
            return 'There was an error adding this operation to Histroy'
        
    else:
        for r in range(0,3):
            row1 = []
            row2 = []
            workingrow = []
            resultrow = []
            for c in range(0,3):
                row1.append(random.randint(0,10))
                row2.append(random.randint(0,10))
                workingrow.append(str(row1[c]) + " + " + str(row2[c]))
                resultrow.append(row1[c]+row2[c])
            matrix1.append(row1)
            matrix2.append(row2)
            working.append(workingrow)
            result.append(resultrow)
    return render_template('addition.html',matrix1=matrix1,matrix2=matrix2,working=working,result=result)


@app.route('/subtraction',methods=['GET','POST'])
@login_required
def subtraction():
    matrix1 = []
    matrix2 = []
    working =[]
    result = []
    if request.method == 'POST':
        for r in range(1,4):
            row1 = []
            row2 = []
            workingrow = []
            resultrow = []
            for c in range(1,4):
                num1 = request.form['M'+str(c)+str(r)]
                num2 = request.form['N'+str(c)+str(r)]
                if num1 != '':
                    row1.append(int(num1))
                else:
                    row1.append(0)
                if num2 != '':
                    row2.append(int(num2))
                else:
                    row2.append(0)
                workingrow.append(str(row1[c-1]) + " - " + str(row2[c-1]))
                resultrow.append(row1[c-1]-row2[c-1])
            matrix1.append(row1)
            matrix2.append(row2)
            working.append(workingrow)
            result.append(resultrow)
        
        record = Record(matrix1=str(matrix1),matrix2=str(matrix2),operation="Subtraction",user_id= current_user.id)

        try:
            db.session.add(record)
            db.session.commit()
        except:
            return 'There was an error adding this operation to Histroy'
    else:
        for r in range(0,3):
            row1 = []
            row2 = []
            workingrow = []
            resultrow = []
            for c in range(0,3):
                row1.append(random.randint(0,10))
                row2.append(random.randint(0,10))
                workingrow.append(str(row1[c]) + " - " + str(row2[c]))
                resultrow.append(row1[c]-row2[c])
            matrix1.append(row1)
            matrix2.append(row2)
            working.append(workingrow)
            result.append(resultrow)

    return render_template('subtraction.html',matrix1=matrix1,matrix2=matrix2,working=working,result=result)



@app.route('/multScal',methods=['GET','POST'])
@login_required
def multScal():
    matrix = []
    working =[]
    result = []
    if request.method == 'POST':
        scalar = request.form['scalar']
        if scalar != '':
            scalar = int(scalar)
        else:
            scalar = 0
        for r in range(1,4):
            row = []
            workingrow = []
            resultrow = []
            for c in range(1,4):
                num = request.form['M'+str(c)+str(r)]
                if num != '':
                    row.append(int(num))
                else:
                    row.append(0)
                workingrow.append(str(row[c-1]) + " x " + str(scalar))
                resultrow.append(row[c-1]*scalar)
            matrix.append(row)
            working.append(workingrow)
            result.append(resultrow)

        scalStr = "Scalar: " + str(scalar)
        record = Record(matrix1=str(matrix),matrix2=scalStr,operation="Multiply with Scalar",user_id=current_user.id)

        try:
            db.session.add(record)
            db.session.commit()
        except:
            return 'There was an error adding this operation to Histroy'
    else:
        scalar = random.randint(1,10)
        for r in range(0,3):
            row = []
            workingrow = []
            resultrow = []
            for c in range(0,3):
                row.append(random.randint(0,10))
                workingrow.append(str(row[c]) + " x " + str(scalar))
                resultrow.append(row[c]*scalar)
            matrix.append(row)
            working.append(workingrow)
            result.append(resultrow)

    return render_template('multScal.html',matrix=matrix,scalar=scalar,working=working,result=result)


@app.route('/matrixMult',methods=['GET','POST'])
@login_required
def matrixMult():
    matrix1 = []
    matrix2 = []
    working =[]
    result = []
    if request.method == 'POST':
        for r in range(1,4):
            row1 = []
            row2 = []
            for c in range(1,4):
                num1 = request.form['M'+str(c)+str(r)]
                num2 = request.form['N'+str(c)+str(r)]
                if num1 != '':
                    row1.append(int(num1))
                else:
                    row1.append(0)
                if num2 != '':
                    row2.append(int(num2))
                else:
                    row2.append(0)
            matrix1.append(row1)
            matrix2.append(row2)
        
        record = Record(matrix1=str(matrix1),matrix2=str(matrix2),operation="Multiplication",user_id=current_user.id)

        try:
            db.session.add(record)
            db.session.commit()
        except:
            return 'There was an error adding this operation to Histroy'
        
    else:
        for r in range(0,3):
            row1 = []
            row2 = []
            for c in range(0,3):
                row1.append(random.randint(0,10))
                row2.append(random.randint(0,10))
            matrix1.append(row1)
            matrix2.append(row2)
    for r1 in range(0,3):
        resultrow = []
        workingrow=[]
        for c2 in range(0,3):
            n = 0
            s = ""
            c1 = 0
            for r2 in range(0,3):
                n = n + (matrix1[r1][c1] * matrix2[r2][c2])
                if s == "":
                    s = s + str(matrix1[r1][c1]) + " x " + str(matrix2[r2][c2])
                else:
                    s = s + " + " + str(matrix1[r1][c1]) + " x " + str(matrix2[r2][c2])
                c1 = c1 + 1 
            resultrow.append(n)
            workingrow.append(s)
        result.append(resultrow)
        working.append(workingrow)

    return render_template('matrixMult.html',matrix1=matrix1,matrix2=matrix2,working=working,result=result)




@app.route('/det',methods=['GET','POST'])
@login_required
def det():
    matrix = []
    if request.method == 'POST':
        for r in range(1,4):
            row = []
            for c in range(1,4):
                num = request.form['M'+str(c)+str(r)]
                if num != '':
                    row.append(int(num))
                else:
                    row.append(0)       
            matrix.append(row)
        
        record = Record(matrix1=str(matrix),matrix2="",operation="Determinant",user_id=current_user.id)

        try:
            db.session.add(record)
            db.session.commit()
        except:
            return 'There was an error adding this operation to Histroy'
        
    else:
        for r in range(0,3):
            row = []
            for c in range(0,3):
                row.append(random.randint(0,10))
            matrix.append(row)

    firstRow = matrix[0]
    twoMone = [[matrix[1][1],matrix[1][2]],[matrix[2][1],matrix[2][2]]]
    twoMtwo = [[matrix[1][0],matrix[1][2]],[matrix[2][0],matrix[2][2]]]
    twoMthree = [[matrix[1][0],matrix[1][1]],[matrix[2][0],matrix[2][1]]]

    det1 = matrix[0][0]* ((matrix[1][1]*matrix[2][2])-(matrix[1][2]*matrix[2][1]))
    s1 = str(matrix[0][0]) + " x ((" + str(matrix[1][1]) + " x " + str(matrix[2][2]) + ") - (" + str(matrix[1][2]) + " x " + str(matrix[2][1]) + "))"
    det2 = matrix[0][1]* ((matrix[1][0]*matrix[2][2])-(matrix[1][2]*matrix[2][0]))
    s2 = str(matrix[0][1]) + " x ((" + str(matrix[1][0]) + " x " + str(matrix[2][2]) + ") - (" + str(matrix[1][2]) + " x " + str(matrix[2][0]) + "))"
    det3 = matrix[0][2]* ((matrix[1][0]*matrix[2][1])-(matrix[1][1]*matrix[2][0]))
    s3 = str(matrix[0][2]) + " x ((" + str(matrix[1][0]) + " x " + str(matrix[2][1]) + ") - (" + str(matrix[1][1]) + " x " + str(matrix[2][0]) + "))"
    det = det1 - det2 +det3


    return render_template('det.html',matrix=matrix,det=det,firstRow=firstRow,twoMone=twoMone,twoMtwo=twoMtwo,twoMthree=twoMthree, s1=s1,s2=s2,s3=s3)



@app.route('/delete/<int:id>')
@login_required
def delete(id):
    record = Record.query.get_or_404(id)

    try:
        db.session.delete(record)
        db.session.commit()
        return redirect('/homepage')
    except:
        return 'There was an error deleting the history record'


@app.route('/view/<int:id>')
@login_required
def view(id):
    record = Record.query.get_or_404(id)
    operation = record.operation
    matrix1 = eval(record.matrix1)
    if(operation == "Multiply with Scalar"):
        lst = (record.matrix2).split(" ")
        matrix2 = int(lst[1])
    elif(operation == "Determinant"):
        matrix2 = ""
    else:
         matrix2 = eval(record.matrix2)
    userID = record.user_id
    working =[]
    result = []
    if(operation == "Addition"):
        for r in range(0,3):
            workingrow = []
            resultrow = []
            for c in range(0,3):
                workingrow.append(str(matrix1[r][c]) + " + " + str(matrix2[r][c]))
                resultrow.append(matrix1[r][c]+matrix2[r][c])
            working.append(workingrow)
            result.append(resultrow)
        return render_template('addition.html',matrix1=matrix1,matrix2=matrix2,working=working,result=result,userID=userID)
    elif(operation == "Subtraction"):
        for r in range(0,3):
            workingrow = []
            resultrow = []
            for c in range(0,3):
                workingrow.append(str(matrix1[r][c]) + " - " + str(matrix2[r][c]))
                resultrow.append(matrix1[r][c]-matrix2[r][c])
            working.append(workingrow)
            result.append(resultrow)
        return render_template('subtraction.html',matrix1=matrix1,matrix2=matrix2,working=working,result=result,userID=userID)
    elif(operation == "Multiply with Scalar"):
        for r in range(0,3):
            workingrow = []
            resultrow = []
            for c in range(0,3):
                workingrow.append(str(matrix1[r][c]) + " x " + str(matrix2))
                resultrow.append(matrix1[r][c]*matrix2)
            working.append(workingrow)
            result.append(resultrow)
        return render_template('multScal.html',matrix=matrix1,scalar=matrix2,working=working,result=result,userID=userID)
    elif(operation == "Multiplication"):
        for r1 in range(0,3):
            resultrow = []
            workingrow=[]
            for c2 in range(0,3):
                n = 0
                s = ""
                c1 = 0
                for r2 in range(0,3):
                    n = n + (matrix1[r1][c1] * matrix2[r2][c2])
                    if s == "":
                        s = s + str(matrix1[r1][c1]) + " x " + str(matrix2[r2][c2])
                    else:
                        s = s + " + " + str(matrix1[r1][c1]) + " x " + str(matrix2[r2][c2])
                    c1 = c1 + 1 
                resultrow.append(n)
                workingrow.append(s)
            result.append(resultrow)
            working.append(workingrow)
        return render_template('matrixMult.html',matrix1=matrix1,matrix2=matrix2,working=working,result=result,userID=userID)
    elif(operation=="Determinant"):
        firstRow = matrix1[0]
        twoMone = [[matrix1[1][1],matrix1[1][2]],[matrix1[2][1],matrix1[2][2]]]
        twoMtwo = [[matrix1[1][0],matrix1[1][2]],[matrix1[2][0],matrix1[2][2]]]
        twoMthree = [[matrix1[1][0],matrix1[1][1]],[matrix1[2][0],matrix1[2][1]]]
        det1 = matrix1[0][0]* ((matrix1[1][1]*matrix1[2][2])-(matrix1[1][2]*matrix1[2][1]))
        s1 = str(matrix1[0][0]) + " x ((" + str(matrix1[1][1]) + " x " + str(matrix1[2][2]) + ") - (" + str(matrix1[1][2]) + " x " + str(matrix1[2][1]) + "))"
        det2 = matrix1[0][1]* ((matrix1[1][0]*matrix1[2][2])-(matrix1[1][2]*matrix1[2][0]))
        s2 = str(matrix1[0][1]) + " x ((" + str(matrix1[1][0]) + " x " + str(matrix1[2][2]) + ") - (" + str(matrix1[1][2]) + " x " + str(matrix1[2][0]) + "))"
        det3 = matrix1[0][2]* ((matrix1[1][0]*matrix1[2][1])-(matrix1[1][1]*matrix1[2][0]))
        s3 = str(matrix1[0][2]) + " x ((" + str(matrix1[1][0]) + " x " + str(matrix1[2][1]) + ") - (" + str(matrix1[1][1]) + " x " + str(matrix1[2][0]) + "))"
        det = det1 - det2 +det3
        return render_template('det.html',matrix=matrix1,det=det,firstRow=firstRow,twoMone=twoMone,twoMtwo=twoMtwo,twoMthree=twoMthree, s1=s1,s2=s2,s3=s3,userID=userID)
    
    return redirect('/')





if __name__ == '__main__':
    app.run(host="127.0.0.1",port=8080,debug=True)
