from decouple import config
from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache
from flask_jwt_extended import JWTManager
import boto3
from flask import Blueprint

cache = Cache(config={'CACHE_TYPE': 'redis', 'CACHE_REDIS_URL': 'redis://redis:6379/0'})
db = SQLAlchemy()
jwt = JWTManager()
s3 = boto3.client('s3', aws_access_key_id=config("AWS_ACCES_KEY"),
                  aws_secret_access_key=config("AWS_SECRET_KEY"))

api = Blueprint('api', __name__, url_prefix='/api')
pub = Blueprint('pub', __name__, url_prefix='/pub')
adm = Blueprint('adm', __name__, url_prefix='/adm')