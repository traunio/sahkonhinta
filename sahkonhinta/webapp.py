import os
import hashlib
import sqlite3
import pandas as pd
from flask import Flask, flash, request, redirect, url_for, render_template, g
from werkzeug.utils import secure_filename
from . import analysis
from datetime import datetime

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}
DATABASE = 'db/sahkonhinta.db'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'salaista'
app.config['DATABASE'] = DATABASE
app.config['MAX_CONTENT_LENGTH'] = 2 * 1000 * 1000  # max upload size 2 MB

# Database connection
def get_db():
    if 'db' not in g:        
        g.db = sqlite3.connect(app.config['DATABASE'])
    return g.db

def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

@app.route('/')
def main_page():

    conn = get_db()

    cursor = conn.cursor()
    cursor.execute('SELECT min(datetime), max(datetime) FROM elspot')
    res = cursor.fetchone()
    first = datetime.strptime(res[0][:10], '%Y-%m-%d').strftime('%d.%m.%Y')
    last = datetime.strptime(res[1][:10], '%Y-%m-%d').strftime('%d.%m.%Y')
    
    return render_template('index.html', first=first, last=last)


@app.route('/consumption/<name>/<float:marginal>')
def results_page(name, marginal):

    try:
        conn = get_db()
        df_db = pd.read_sql('select * from elspot',
                            conn,
                            index_col='datetime',
                            parse_dates=['datetime'])
        
        results = analysis.analyze(os.path.join(app.config['UPLOAD_FOLDER'], name), df_db, marginal)
        
    except:
        return f'<p>Jotain meni pieleen. Tiedosto oli {name}</p>'


    return render_template('success.html', outcome=results)


@app.route('/consumption/<name>')
def results_const(name):
    return results_page(name, 0.42)


@app.route('/upload', methods=['POST'])
def upload():

    # check if the post request has the file part
    if 'file' not in request.files:
        print(f"request.files={request.files}\nrequesst={request}")
        flash('Tiedosto puuttuu')
        return redirect(request.url)

    file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
    if file.filename == '':
        flash('Tiedostoa ei ole valittu')
        return redirect(url_for('main_page'))

    if file and allowed_extension(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        md5sum = hashlib.md5()
        with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'rb') as f:
            bytes = f.read()
            md5sum.update(bytes)

        md5name = md5sum.hexdigest()
        os.rename(os.path.join(app.config['UPLOAD_FOLDER'], filename),
                  os.path.join(app.config['UPLOAD_FOLDER'], md5name))


        marginal = request.form.get('marginal')
        if marginal:
            marginal = float(marginal.replace(',', '.'))
        else:
            marginal = 0.42
            
        return redirect(url_for('results_page', name=md5name, marginal=marginal))
        


def allowed_extension(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'



    
