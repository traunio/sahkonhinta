import os
import hashlib
from datetime import datetime
import pandas as pd
from flask import request, redirect, url_for, render_template, Blueprint, current_app
from werkzeug.utils import secure_filename
from sahkonhinta.db import get_db
from . import analysis


bp = Blueprint('webapp', __name__)


@bp.route('/')
def main_page():  # pylint: disable=C0116

    conn = get_db()

    cursor = conn.cursor()
    cursor.execute('SELECT min(datetime), max(datetime) FROM elspot')
    res = cursor.fetchone()
    first = datetime.strptime(res[0][:10], '%Y-%m-%d').strftime('%d.%m.%Y')
    last = datetime.strptime(res[1][:10], '%Y-%m-%d').strftime('%d.%m.%Y')

    return render_template('index.html', first=first, last=last)


@bp.route('/consumption/<name>')
def results_page(name):  # pylint: disable=C0116


    start = request.args.get('first', '')
    end = request.args.get('last', '')
    marginal_s = request.args.get('margin', '0.42')

    try:
        conn = get_db()
        df_db = pd.read_sql('select * from elspot',
                            conn,
                            index_col='datetime',
                            parse_dates=['datetime'])

        results, spot_profile = analysis.analyze(os.path.join(current_app.config['UPLOAD_FOLDER'],
                                                              name)
                                                 ,df_db
                                                 ,marginal_s
                                                 ,start
                                                 ,end)

    except Exception:  # pylint: disable=W0703
        return render_template('error.html')


    return render_template('success.html',
                           outcome=results,
                           spot=spot_profile,
                           marginal_s=marginal_s.replace('.', ','))


@bp.route('/upload', methods=['POST'])
def upload():  # pylint: disable=C0116, R1710

    # check if the post request has the file part
    if 'file' not in request.files:
        print(f"request.files={request.files}\nrequesst={request}")
        return redirect(request.url)

    file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
    if file.filename == '':

        return redirect(url_for('webapp.main_page'))

    if file and allowed_extension(file.filename):
        filename = secure_filename(file.filename)
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(full_path)

        try:
            df = pd.read_csv(full_path, sep=';', decimal=',', usecols=['Alkuaika','Määrä'])
            df.to_csv(full_path, sep=';', index=False)
        except:  # pylint: disable=W0702
            print('Dataframen lukemisessa häikkää')

        md5sum = hashlib.md5()
        with open(full_path, 'rb') as f:
            all_bytes = f.read()
            md5sum.update(all_bytes)

        md5name = md5sum.hexdigest()
        os.rename(full_path,
                  os.path.join(current_app.config['UPLOAD_FOLDER'], md5name))

        marginal = request.form.get('marginal')
        if marginal:
            marginal = float(marginal.replace(',', '.'))
        else:
            marginal = 0.42

        return redirect(url_for('webapp.results_page', name=md5name, marginal=marginal))


@bp.errorhandler(404)
def some_error(error):  # pylint: disable=C0116, W0613
    return render_template('404.html')

def allowed_extension(filename):  # pylint: disable=C0116
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'
