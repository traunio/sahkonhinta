import json
import pandas as pd


MARGINAL = 0.42  # marginal if nothing provided

def read_consumption(filename):
    """Transforms uploaded csv file to dataframe

    :param filename: filename with path to uploaded csv
    """

    try:
        df = pd.read_csv(filename, sep=';')
        df.index = pd.to_datetime(df.Alkuaika)
        df.index = df.index.tz_convert('Europe/Helsinki')

        df = df['Määrä']
        df.name = 'consumed'
    except Exception as exc:
        print('Something went wrong. Too bad. Bad upload probably')
        raise Exception('Something went wrong with reading csv') from exc

    if len(df) == 0:
        raise Exception('Consumption csv is empty')

    return df


def parse_marginal(marginal):
    """Helper function to parse float string to marginal. Accepts comma and
    full stop as decimal separator
    :param marginal: marginal to parse
    :returns: float marginal or MARGINAL if not possible
    """

    try:
        result = float(marginal.replace(',', '.'))
    except ValueError:
        result = MARGINAL

    return result


def parse_date(date):
    """Helper function to parse dates
    :param date: Date given as string
    :returns: date as pd.Datetime object or None
    """

    try:
        temp = pd.to_datetime(date, dayfirst=True)
        result = pd.Timestamp(temp, tz='Europe/Helsinki')
    except ValueError:
        result = None

    return result



def analyze(filename, df_db, marginal, start=None, end=None):
    """The main function of this file. Called by flask, and return a dict
    with the wanted answers

    :param filename: filename with path to the uploaded csv
    :param marginal: Marginal added snt/kWh for spot electricity
    :param start: first date to use in user supplied data
    :param end: last date to use in user supplied data
    :returns: all chart data and numerical results in a dict
    """

    if isinstance(marginal, str):
        marginal = parse_marginal(marginal)

    consumption = read_consumption(filename)
    delta = pd.Timedelta(23, 'H')

    if start:
        start = parse_date(start)
        if len(consumption[start:]) > 1:
            consumption = consumption[start:]
    if end:
        end = parse_date(end) + delta
        if len(consumption[:end]) > 1:
            consumption = consumption[:end]

    prices = df_db

    res = prices.merge(consumption, left_index=True, right_index=True)
    res['costs'] = ((res.price+marginal) * res.consumed)/100  # euros

    outcome = {}

    # keskimääräinen tuntihinta koko kulutukselle
    outcome['const_price_s'] = f'{res.costs.sum() / res.consumed.sum():.2f}'.replace('.', ',')
    outcome['const_price'] = res.costs.sum() / res.consumed.sum()

    outcome['begin'] = res.index[0].strftime('%d.%m.%Y')
    outcome['end'] = res.index[-1].strftime('%d.%m.%Y')
    outcome['first'] = res.index[0].strftime('%Y-%m-%d')
    outcome['last'] = res.index[-1].strftime('%Y-%m-%d')

    outcome['tot_power'] = res.consumed.sum()
    outcome['tot_power_s'] = f'{outcome["tot_power"]:.2f}'.replace('.', ',')
    outcome['tot_price'] = res.costs.sum()
    outcome['tot_price_s'] = f'{outcome["tot_price"]:.2f}'.replace('.', ',')


    # weeklyPrice kuvaajan data
    temp = (res.costs.resample("W").sum() / res.consumed.resample("W").sum()) * 100
    outcome['weekPrice'] = json.dumps([round(val, 1) for val in temp.values.tolist()])
    outcome['weekX'] = json.dumps(temp.index.strftime('%Y-%m-%d').tolist())

    # weeklyPrice - päivätaso
    temp = (res.costs.resample("D").sum() / res.consumed.resample("D").sum()) * 100
    outcome['dayPrice'] = json.dumps([round(val, 1) for val in temp.values.tolist()])
    outcome['dayX'] = json.dumps(temp.index.strftime('%Y-%m-%d').tolist())

    # weeklyPrice kuukausitaso
    temp = (res.costs.resample("M", label="left", closed="left").sum() \
            / res.consumed.resample("M", label="left", closed="left").sum()) * 100
    outcome['monthPrice'] = json.dumps([round(val,1) for val in temp.values.tolist()])
    outcome['monthX'] = json.dumps(temp.index.strftime('%Y-%m-%d').tolist())

    # usageHisto sähkönkulutuksen histogrammi
    consumed = res.consumed.resample("D").sum()
    length = consumed.max() - consumed.min()
    bins = min([10, int(length/2)])

    counts = pd.cut(consumed, bins, precision=0).value_counts().sort_index()
    xlabels = list(f"{int(a.left)}...{int(a.right)}" for a in counts.index)
    ylabels = counts.values.tolist()
    outcome['Dlabels'] = xlabels
    outcome['Dvalues'] = ylabels

    # profile - Keskimääräinen päiväkulutus
    def quartile1(values):
        return values.quantile(0.1)

    def quartile3(values):
        return values.quantile(0.9)

    aggs = ['mean', quartile1, quartile3]

    temp = res.consumed.groupby(res.index.hour).agg(aggs)
    outcome['profileMean'] = json.dumps([round(val, 3) for val in temp['mean'].values.tolist()])
    outcome['profileq1'] = json.dumps([round(val, 3) for val in temp['quartile1'].values.tolist()])
    outcome['profileq3'] = json.dumps([round(val, 3) for val in temp['quartile3'].values.tolist()])
    outcome['profilex'] = json.dumps(temp.index.values.tolist())

    return outcome
