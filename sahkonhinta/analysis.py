import pandas as pd
import json
from pathlib import Path

PRICES = Path('misc/prices.csv')


def read_consumption(filename):
    """Transforms uploaded csv file to dataframe

    :param filename: filename with path to uploaded csv
    """

    try: 
        df = pd.read_csv(filename, sep=';', decimal=',', usecols=['Alkuaika','Määrä'])
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


def resampling_rate(index):
    """Helper function to choose between appropriate resampling for results.

    If the data is less than a day, then resampling 'H", less than 30 days "D", 
    and otherwise "M"

    :param index: dataframe's index for the results range
    """

    difference = index[-1] - index[0]

    if difference.days <= 1:
        return "H"
    if difference.days <=30:
        return "D"
    
    return "W"
    
    
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

    rate = resampling_rate(res.index)
    outcome['price_time_y'] = json.dumps((res.costs.resample(rate).sum() /
                             res.consumed.resample(rate).sum()).values.tolist())

    outcome['price_time_x'] = (res.costs.resample(rate).sum() /
                             res.consumed.resample(rate).sum()).index

    # dayUsage histogrammin data
    outcome['usage'] = json.dumps(res.consumed.resample("D").sum().values.tolist())
    res['diffis'] = res.costs - res.consumed * outcome['const_price']

    # priceDiff histogrammin data
    outcome['diffis'] = json.dumps(res.diffis.resample("D").sum().values.tolist())

    # weeklyPrice kuvaajan data
    temp = (res.costs.resample("W").sum() / res.consumed.resample("W").sum()) * 100
    outcome['weekPrice'] = json.dumps(temp.values.tolist())
    outcome['weekX'] = json.dumps(temp.index.strftime('%Y-%m-%d').tolist())
    temp = (res.costs.resample("D").sum() / res.consumed.resample("D").sum()) * 100
    outcome['dayPrice'] = json.dumps(temp.values.tolist())
    outcome['dayX'] = json.dumps(temp.index.strftime('%Y-%m-%d').tolist())

    # kuukausitaso
    temp = (res.costs.resample("M", label="left", closed="left").sum() \
            / res.consumed.resample("M", label="left", closed="left").sum()) * 100
    outcome['monthPrice'] = json.dumps(temp.values.tolist())
    outcome['monthX'] = json.dumps(temp.index.strftime('%Y-%m-%d').tolist())
    
        
    return outcome
