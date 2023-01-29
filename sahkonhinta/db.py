"""Database related functions for fetching ENTSOE price data.
"""

import sqlite3
from pathlib import Path
import pandas as pd
from entsoe import EntsoePandasClient
from flask import current_app, g


START = '20210901'   # the first day of ELSPOT that we are interested in
VAT_START = '20221201 00:00:00'  # the first day of 10% VAT
VAT_END = '20230430 23:59:00'  # the last day of 10% VAT

def get_db():
    """Gets connection object from g"""

    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])

    return g.db

def get_elspot():
    """Function return elspot price data as a datarame
    :returns: pandas dataframe with all elspot data
    """

    with get_db() as conn:
        df_db = pd.read_sql('select * from elspot',
                            conn,
                            index_col='datetime',
                            parse_dates=['datetime'])
        df_db.index = df_db.index.tz_localize('UTC').tz_convert('Europe/Helsinki')

    return df_db

def refresh_elspot_db(start, end, conn, if_exists='append'):
    """Function to add new price data to elspot database. VAT/ALV is added to
    price date from ENTSOE. In Finland it is 10% between 20221201 and 20230430,
    otherwise 24%. Price data is also converted to snt/kWh from €/MWh
    :param start: the start pandas Timestamp
    :param end: the end pandas Timestamp. Note also clock time should be included
    :param conn: connection to database
    :param if_exists: what to do with database addition
    """

    api_key = current_app.config['ENTSOE']
    client = EntsoePandasClient(api_key=api_key)
    country_code = 'FI'
    res = client.query_day_ahead_prices(country_code, start=start,end=end)
    df = res.reset_index()  # pylint: disable=C0103
    df.columns = ['datetime', 'price']

    selector = df.datetime.between(VAT_START, VAT_END)

    # here we apply VAT/ALV based on the date and make price snt/kWh
    df.loc[selector, 'price'] = df[selector].price * 1.1 / 10
    df.loc[~selector, 'price'] = df[~selector].price * 1.24 / 10
    df.price = df.price.apply(lambda x: round(x,3))
    df['datetime'] = df.datetime.apply(lambda x: x.timestamp())

    if df.to_sql('elspot', conn, if_exists=if_exists, index=False):
        conn.commit()
        return True

    return None


def get_db_dates():
    """Function used by main_page view. Returns first and last day of database
    and updates the database, if there are newer price data available
    :return: Tuple of (first, last) strings of db dates"""

    with get_db() as conn:

        cursor = conn.cursor()
        cursor.execute('SELECT min(datetime), max(datetime) FROM elspot')
        res = cursor.fetchone()

        first = pd.Timestamp(res[0], tz='Europe/Helsinki', unit='s')
        last = pd.Timestamp(res[1], tz='Europe/Helsinki', unit='s')


        first_missing = last + pd.Timedelta(1, 'h')
        today_last = pd.Timestamp.today(tz='Europe/Helsinki').replace(
            hour=23, minute=59, second=0)

        if today_last - first_missing > pd.Timedelta(18, "h"):
            refresh_elspot_db(first_missing, today_last, conn)
            cursor.execute('SELECT min(datetime), max(datetime) FROM elspot')
            res = cursor.fetchone()

            first = pd.Timestamp(res[0], tz='Europe/Helsinki')
            last = pd.Timestamp(res[1], tz='Europe/Helsinki')
            remove_old_files()


    first = first.strftime('%d.%m.%Y')
    last = last.strftime('%d.%m.%Y')

    return first, last


def remove_old_files():
    """Helper function to remove old consumption files saved in uploads.
    Removes things that are older than a week.
    """

    upload_path = Path(current_app.config['UPLOAD_FOLDER'])
    files = list(x for x in upload_path.glob('*') if '.' not in x.name
                 and x.name!='example_results')


    cutoff = pd.Timestamp.now() - pd.Timedelta(7, "d")

    # Note pd.Timestamp constructed from name.stat().st_mtime will be in GMT time
    # So the exact difference might be 7 days minus couple hours
    to_remove = list(name for name in files
                     if pd.Timestamp(name.stat().st_mtime, unit='s') < cutoff)


    # Removing files
    for name in to_remove:
        name.unlink()


def first_missing_time():
    """Return the newest datetime in the database plus 1 h as pandas Timestamp

    If nothing in database, return None"""

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT max(datetime) FROM elspot')
    try:
        latest = cursor.fetchone()[0]
    except IndexError:
        return None

    date = pd.Timestamp(latest, tz='Europe/Helsinki', unit='s') + pd.Timedelta('01:00:00')

    conn.close()

    return date


def init_db():
    """Initializes the database by fetching prices between
    START date and current day. Then uploads these to database, and replaces
    the current database (if exists)"""

    start = pd.Timestamp(START, tz='Europe/Helsinki')
    end = pd.Timestamp(pd.Timestamp.today(tz='Europe/Helsinki').date(),
                       tz='Europe/Helsinki') + pd.Timedelta('23:59:00')

    conn = get_db()
    return refresh_elspot_db(start, end, conn, 'replace')



def close_db(e=None):  # pylint: disable=C0114, C0103, W0613
    """Closes the database. Code based on example on flask website"""
    db = g.pop('db', None)  # pylint: disable=C0103

    if db is not None:
        db.close()


def init_app(app):  # pylint: disable=C0116
    app.teardown_appcontext(close_db)
