"""Database related functions for fetching ENTSOE price data
"""

import sqlite3
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

def refresh_elspot_db(start, end, if_exists='append'):
    """Function to add new price data to elspot database. VAT/ALV is added to
    price date from ENTSOE. In Finland it is 10% between 20221201 and 20230430,
    otherwise 24%.
    :param start: the start pandas Timestamp
    :param end: the end pandas Timestamp. Note also clock time should be included
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

    conn = get_db()

    if df.to_sql('elspot', conn, if_exists=if_exists, index=False):
        conn.commit()
        return True

    return None


def first_missing_time():
    """Return the newest datetime in the database plus 1 h as pandas Timestamp

    If nothing in database, return None"""

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT datetime from elspot order by datetime desc limit 1')
    try:
        latest = cursor.fetchone()[0]
    except IndexError:
        return None

    date = pd.Timestamp(latest[0]) + pd.Timedelta('01:00:00')
    date = date.tz_convert('Europe/Helsinki')
    conn.close()

    return date


def init_db():
    """Initializes the database by fetching prices between
    START date and current day. Then uploads these to database, and replaces
    the current database (if exists)"""

    start = pd.Timestamp(START, tz='Europe/Helsinki')
    end = pd.Timestamp(pd.Timestamp.today(tz='Europe/Helsinki').date(),
                       tz='Europe/Helsinki') + pd.Timedelta('23:59:00')

    return refresh_elspot_db(start, end, 'replace')



def close_db(e=None):  # pylint: disable=C0114, C0103, W0613
    """Closes the database. Code based on example on flask website"""
    db = g.pop('db', None)  # pylint: disable=C0103

    if db is not None:
        db.close()


def init_app(app):  # pylint: disable=C0116
    app.teardown_appcontext(close_db)
