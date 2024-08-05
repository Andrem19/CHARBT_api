from flask import Flask, g, request, url_for
from __init__ import db, cache, jwt, s3, api, pub, adm
from decouple import config
import os
import logging
from datetime import datetime
from flask import jsonify
from flask_cors import CORS
from flask import request
import helpers.services as serv
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import BlackList, User, Admin, AllowedIp, data_seed
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_apscheduler import APScheduler

class Config(object):
    JOBS = [
        {
            'id': 'job1',
            'func': 'main:job_1',
            'args': (),
            'trigger': 'interval',
            'hours': 24 #'seconds': 60*60 \\'hours': 24 \\'days': 7
        }
    ]
def job_1():
        print("The task exacute every minute")

def datetimeformat(value, format='%m-%d %H:%M:%S'):
    return datetime.fromtimestamp(value).strftime(format)

@jwt_required(optional=True)
def check_jwt():
    if request.method != 'OPTIONS':
        identity = get_jwt_identity()
        if identity is None:
            return "Not Found", 404  # Если JWT токен отсутствует, возвращаем 404 ошибку

        user_id = identity['user_id']
        session_code = identity['session_code']
        user = Admin.query.get(user_id)
        g.admin = user
        if not user or user.sessionCode != session_code:
            # Если пользователь не найден или токен сессии не совпадает, возвращаем 404 ошибку
            return "Not Found", 404
        # ip_list = [u.ip for u in g.admin.allowed_ip]
        # print(ip_list, g.client_ip)
        # if g.client_ip not in ip_list:
        #     return "Not Found", 404

def create_app():
    app = Flask(__name__)
    CORS(app, origins=['http://localhost:3000', 'http://localhost:5000', 'https://charbt.com', 'https://www.charbt.com'], supports_credentials=True)
    app.secret_key = config("SECRET_KEY")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://charbt:Oad106zfyvjo@charbtdb.cjgkvj8ubags.eu-west-2.rds.amazonaws.com:5432/charbt_db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_COOKIE_CSRF_PROTECT'] = False
    # app.config['JWT_CSRF_IN_COOKIES'] = True
    app.config['JWT_TOKEN_LOCATION'] = ['headers', 'cookies']
    app.jinja_env.filters['datetime'] = datetimeformat
    db.init_app(app)
    cache.init_app(app)
    jwt.init_app(app)

    app.config.from_object(Config())

    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()


    # @app.after_request
    # def after_request(response):
    #     allowed_origins = ['http://localhost:3000', 'http://localhost:5000', 'https://charbt.com' ]
    #     origin = request.headers.get('Origin')
    #     if origin in allowed_origins:
    #         response.headers.add('Access-Control-Allow-Origin', origin)
    #     response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-CSRF-TOKEN')
    #     response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    #     response.headers.add('Access-Control-Allow-Credentials', 'true')
    #     return response
    
    def check_ip_in_blacklist(ip):
        blacklist = BlackList.query.filter_by(ip=ip).first()
        if blacklist and blacklist.to >= datetime.now():
            return True, jsonify({'message': 'Your IP is banned until ' + blacklist.to.strftime('%Y-%m-%d %H:%M:%S')}), 403
        return False, None, None
    
    
    
    with app.app_context():
        
        try:
            # db.drop_all()
            # db.create_all()
            # data_seed()
            pass
        except Exception as e:
            logging.info(e)

    import routes.pub
    import routes.api
    import routes.auth
    import routes.sub
    import routes.blog
    import routes.admin

    @pub.before_request
    def before_request_pub():
        g.client_ip = request.remote_addr
        is_banned, response, status_code = check_ip_in_blacklist(g.client_ip)
        if is_banned:
            return response, status_code

    @adm.before_request
    def before_request_adm():
        g.client_ip = request.remote_addr
        allowedIp = AllowedIp.query.all()
        ip_list = [u.ip for u in allowedIp]
        # if g.client_ip not in ip_list:
        #     return "Not Found", 404
        
        is_banned, response, status_code = check_ip_in_blacklist(g.client_ip)
        if is_banned:
            return response, status_code

        # Пропустить проверку JWT для эндпоинта /login
        if request.path != url_for('adm.login'):
            return check_jwt()

        

    @api.before_request
    @jwt_required()
    def before_request_api():
        g.client_ip = request.remote_addr
        is_banned, response, status_code = check_ip_in_blacklist(g.client_ip)
        if is_banned:
            return response, status_code
        
        if request.method != 'OPTIONS':
            try:
                identity = get_jwt_identity()
                if identity is not None:
                    user_id = identity['user_id']
                    session_code = identity['session_code']
                    user = User.query.get(user_id)
                
                if not user:
                    return jsonify({'message': 'User not found or jwt token not valid'}), 407
                if session_code != user.sessionCode:
                    return jsonify({'message': 'User_Session not found'}), 407
                if g.client_ip != user.login_ip:
                    return jsonify({'message': 'Login ip was changed please log in'}), 407
                g.user = user

            except Exception as e:
                print(e)
                return jsonify({'message': 'An error occurred: ' + str(e)}), 500

    
    app.register_blueprint(pub)
    app.register_blueprint(api)
    app.register_blueprint(adm)
    

    serv.download_dir('SERVER_SET/MAPS', '/app', 'charbtmarketdata', s3)
    file_name = '1577836800000_1717113600000.csv'
    s3.download_file('charbtmarketdata', 'SERVER_SET/BTCUSDT/1d/' + file_name, os.path.join('/app/SERVER_SET', file_name))

    return app

app = create_app()

#логи:
# --1000 вход выход
# --2000 смена имейла смена пароля
# --3000 оплата отмена подписки
# --4000 создание тикета
# --5000 изменение аварара изменение ника
# --6000 пересылка токенов
# --7000 покупка за токены
# --8000 запрос данных (пара и таймфрейм)