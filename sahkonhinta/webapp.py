import os
import hashlib
import pandas as pd
from flask import request, redirect, url_for, render_template, Blueprint, current_app, flash
from werkzeug.utils import secure_filename
from sahkonhinta.db import get_db_dates, get_elspot
from . import analysis


bp = Blueprint('webapp', __name__)


@bp.route('/')
def main_page():  # pylint: disable=C0116

    first, last = get_db_dates()

    return render_template('index.html', first=first, last=last)


@bp.route('/consumption/<name>')
def results_page(name):  # pylint: disable=C0116


    start = request.args.get('first', '')
    end = request.args.get('last', '')
    marginal_s = request.args.get('margin', '0.42')

    try:
        df_db = get_elspot()
        results, spot_profile = analysis.analyze(os.path.join(current_app.config['UPLOAD_FOLDER'],
                                                              name)
                                                 ,df_db
                                                 ,marginal_s
                                                 ,start
                                                 ,end)

    except Exception:  # pylint: disable=W0703
        flash("Ongelma ladattujen tietojen ja sähköpörssin hintojen vertailussa")
        return render_template('error.html')


    return render_template('success.html',
                           outcome=results,
                           name=name,
                           spot=spot_profile,
                           marginal_s=marginal_s.replace('.', ','))


@bp.route('/upload', methods=['POST'])
def upload():  # pylint: disable=C0116, R1710

    # check if the post request has the file part
    if 'file' not in request.files:
        flash("Sivupyyntö ei sisältänyt tiedostoa")
        return redirect(url_for('webapp.main_page'))

    file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
    if file.filename == '':

        flash("Tedostoa ei saatu")
        return redirect(url_for('webapp.main_page'))

    if file and allowed_extension(file.filename):
        filename = secure_filename(file.filename)
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(full_path)

        try:
            df = pd.read_csv(full_path, sep=';', decimal=',', usecols=['Alkuaika','Määrä'])
            df.to_csv(full_path, sep=';', index=False)
        except:  # pylint: disable=W0702
            flash("Jotain meni pieleen ladatun csv-tiedoston käsitelyssä."
                  " Löytyyhän siitä 'Alkuaika' ja 'Määrä' kolumnit?")
            os.remove(full_path)
            return redirect(url_for('webapp.main_page'))

        md5sum = hashlib.md5()
        with open(full_path, 'rb') as f:
            all_bytes = f.read()
            md5sum.update(all_bytes)

        md5name = md5sum.hexdigest()
        os.rename(full_path,
                  os.path.join(current_app.config['UPLOAD_FOLDER'], md5name))

        marginal = request.form.get('margin')
        if marginal:
            marginal = float(marginal.replace(',', '.'))
        else:
            marginal = 0.42

        return redirect(url_for('webapp.results_page', name=md5name, margin=marginal))

    flash("Jotain meni pieleen. Oliko tiedoston pääte muu kuin '.csv'?")
    return redirect(url_for('webapp.main_page'))

@bp.route('/delete/<name>')
def delete_user_data(name):  # pylint: disable=C0116

    if all(chr in '0123456789abcdef' for chr in name):

        filename = os.path.join(current_app.config['UPLOAD_FOLDER'], name)

        if os.path.isfile(filename):

            os.remove(filename)
            flash(f"Tulokset '{name}' poistettu onnistuneesti")
            return redirect(url_for('webapp.main_page'))

    flash("Tuloksia ei löytynyt.")
    return redirect(url_for('webapp.main_page'))


@bp.errorhandler(404)
def some_error(error):  # pylint: disable=C0116, W0613
    return render_template('404.html')

def allowed_extension(filename):  # pylint: disable=C0116
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'
