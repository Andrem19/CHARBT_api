import numpy as np
from __init__ import s3
import os
import uuid
import json

async def get_json_data(coin, timeframe):
    tm = ''

    if timeframe == 60:
        tm = '1h'
    elif timeframe == 1440:
        tm = '1d'
    else:
        tm = f'{timeframe}m'
    filename = f'/app/SERVER_SET/MAPS/{coin}_{tm}.json'

    with open(filename, 'r') as f:
        data = json.load(f)

    return data


async def get_csv_data(path):
    data = np.genfromtxt(path, delimiter=',')
    return data

async def load_data_sets(path: str):
    d = await get_csv_data(path)

    return d



async def get_csv_data_s3(bucket, key):
    # Generate a unique filename for each request
    file_path = f'/app/SERVER_SET/{uuid.uuid4()}.csv'
    s3.download_file(bucket, key, file_path)
    data = np.genfromtxt(file_path, delimiter=',')
    
    # Delete the file after reading it
    os.remove(file_path)
    
    return data

async def load_data_sets_s3(path):
    bucket = 'charbtmarketdata'
    d = await get_csv_data_s3(bucket, path)

    return d



