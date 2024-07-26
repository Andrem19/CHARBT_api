from decouple import config
import boto3
import os

s3 = boto3.client('s3', aws_access_key_id=config("AWS_ACCES_KEY"),
                  aws_secret_access_key=config("AWS_SECRET_KEY"))

base_data = 'D:\\PYTHON\\MARKET_DATA\\_crypto_data'
bucket = 'charbtmarketdata'

COIN_SET = [
    'AAVEUSDT',
    'ADAUSDT',
    'ALGOUSDT',
    'APTUSDT',
    'ARBUSDT',
    'ATOMUSDT',
    'AVAXUSDT',
    'BNBUSDT',
    'BTCUSDT',
    'DOTUSDT',
    'DOGEUSDT',
    'DYDXUSDT',
    'ETHUSDT',
    'FILUSDT',
    'FTMUSDT',
    'GALAUSDT',
    'GRTUSDT',
    'KAVAUSDT',
    'LINKUSDT',
    'LTCUSDT',
    'MANAUSDT',
    'MATICUSDT',
    'QNTUSDT',
    'SOLUSDT',
    'TRXUSDT',
    'UNIUSDT',
    'VETUSDT',
    'XLMUSDT',
    'XMRUSDT',
    'XRPUSDT',
]
timeframes = [
    '1m',
    '5m',
    '1h',
    '1d'
]

def upload_files(path, bucket, s3_path):
    for subdir, dirs, files in os.walk(path):
        for file in files:
            full_path = os.path.join(subdir, file)
            with open(full_path, 'rb') as data:
                s3.upload_fileobj(data, bucket, s3_path)

for coin in COIN_SET:
    path = os.path.join(base_data, coin)
    for t in timeframes:
        upload_files(path, bucket, f'MARKET_DATA/_crypto_data/{coin}/{coin}_{t}.csv')

