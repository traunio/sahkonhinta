import pandas as pd
import json
from pathlib import Path

PRICES = Path('misc/prices.csv')


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
    except:
        print('Something went wrong. Too bad. Bad upload probably')
        raise Exception('Something went wrong with reading csv')

    if len(df) == 0:
        raise Exception('Consumption csv is empty')

    return df


def analyze(filename, df_db, marginal):
    """The main function of this file. Called by flask, and return a dict
    with the wanted answers

    :param filename: filename with path to the uploaded csv
    :param marginal: Marginal added snt/kWh for spot electricity
    :returns: all chart data and numerical results in a dict
    """

    # marginaali myöhemmin
    consumption = read_consumption(filename)
    prices = df_db

    res = prices.merge(consumption, left_index=True, right_index=True)
    res['costs'] = ((res.price+marginal) * res.consumed)/100  # euros

    outcome = dict()

    # keskimääräinen tuntihinta koko kulutukselle
    outcome['const_price_s'] = f'{res.costs.sum() / res.consumed.sum():.2f}'
    outcome['const_price'] = res.costs.sum() / res.consumed.sum()

    outcome['begin'] = res.index[0].strftime('%d.%m.%Y')
    outcome['end'] = res.index[-1].strftime('%d.%m.%Y')
    outcome['first'] = res.index[0].strftime('%Y-%m-%d')
    outcome['last'] = res.index[-1].strftime('%Y-%m-%d')

    outcome['tot_power'] = res.consumed.sum()
    outcome['tot_power_s'] = f'{outcome["tot_power"]:.2f}'
    outcome['tot_price'] = res.costs.sum()
    outcome['tot_price_s'] = f'{outcome["tot_price"]:.2f}'


    # weeklyPrice kuvaajan data
    temp = (res.costs.resample("W").sum() / res.consumed.resample("W").sum()) * 100
    outcome['weekPrice'] = json.dumps(temp.values.tolist())
    outcome['weekX'] = json.dumps(temp.index.strftime('%Y-%m-%d').tolist())

    # weeklyPrice - päivätaso
    temp = (res.costs.resample("D").sum() / res.consumed.resample("D").sum()) * 100
    outcome['dayPrice'] = json.dumps(temp.values.tolist())
    outcome['dayX'] = json.dumps(temp.index.strftime('%Y-%m-%d').tolist())

    # weeklyPrice kuukausitaso
    temp = (res.costs.resample("M", label="left", closed="left").sum() \
            / res.consumed.resample("M", label="left", closed="left").sum()) * 100
    outcome['monthPrice'] = json.dumps(temp.values.tolist())
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
    def q1(x):
        return x.quantile(0.1)

    def q3(x):
        return x.quantile(0.9)

    aggs = ['mean', q1, q3]

    temp = res.consumed.groupby(res.index.hour).agg(aggs)
    outcome['profileMean'] = json.dumps(temp['mean'].values.tolist())
    outcome['profileq1'] = json.dumps(temp['q1'].values.tolist())
    outcome['profileq3'] = json.dumps(temp['q3'].values.tolist())
    outcome['profilex'] = json.dumps(temp.index.values.tolist())

    return outcome
