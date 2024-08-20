from models import Position, Session, GlobalSettings
import logging
import helpers.get_data as gd
import asyncio
from flask import send_file
import csv
import os
import random
import numpy as np
import string
import os
from flask import jsonify, request, jsonify, g, after_this_request
from botocore.exceptions import BotoCoreError, ClientError
import random
from functools import wraps
from flask_jwt_extended import jwt_required
from __init__ import db, s3, cache, api
import helpers.services as serv
from werkzeug.utils import secure_filename

logging.basicConfig(level=logging.INFO)


@api.route('/session/<int:session_id>', methods=['GET'])
def get_session(session_id):

    session = Session.query.get(session_id)
    if not session:
        return jsonify({'message': 'Session not found'}), 404

    positions_data = [{'id': position.id, 'session_id': position.session_id, 'volatility': position.volatility, 'amount': position.amount, 'open_time': position.open_time, 'close_time': position.close_time, 'open_price': position.open_price, 'user_id': position.user_id, 'timeframe': position.timeframe, 'close_price': position.close_price, 'type_of_close': position.type_of_close, 'coin_pair': position.coin_pair, 'profit': position.profit, 'buy_sell': position.buy_sell} for position in session.positions]
    session_data = {'id': session.id, 'decimal_places': session.decimal_places, 'selfDataId': session.selfdataid, 'is_self_data': session.is_self_data, 'coin_pair': session.coin_pair, 'timeframe': session.timeframe, 'additional_timaframe': session.additional_timaframe, 'cursor': session.cursor, 'balance': session.balance, 'current_PnL': session.current_PnL, 'positions': positions_data}

    g.user.current_session_id = int(session_id)
    db.session.commit()

    return jsonify(session_data), 200

@api.route('/position/<int:position_id>', methods=['GET'])
def get_position(position_id):

    position = Position.query.get(position_id)
    if not position:
        return jsonify({'message': 'Position not found'}), 404

    position_data = {
        'id': position.id,
        'balance': position.balance,
        'coin_pair': position.coin_pair,
        'open_price': position.open_price,
        'close_price': position.close_price,
        'profit': position.profit,
        'open_time': position.open_time,
        'timeframe': position.timeframe,
        'close_time': position.close_time,
        'amount': position.amount,
        'volatility': position.volatility,
        'user_id': position.user_id,
        'target_len': position.target_len,
        'type_of_close': position.type_of_close,
        'buy_sell': position.buy_sell
    }

    return jsonify(position_data), 200

@api.route('/add_session', methods=['POST'])
def add_session():
    try:
        if g.user.payment_status == 'default':
            return jsonify({'message': 'User has default status'}), 404
        
        session_limit = {
            'default': 1,
            'essential': 10,
            'premium': 50,
            'premium-plus': 100
        }
        if session_limit[g.user.payment_status]<= g.user.sessions.count():
            return jsonify({'message': 'The number of sessions has reached the limit'}), 400

        
        session_name = request.json.get('name', f'{g.user.username}_{serv.random_string().upper()}')
        coin_pair = request.json.get('coin_pair', 'BTCUSDT')
        timeframe = int(request.json.get('timeframe', 1440))
        is_self_data = request.json.get('is_self_data', False)
        data_id = request.json.get('data_id', 0)
        decimal_places = int(request.json.get('decimal_places', 2))
        if is_self_data:
            timeframe = 60
        adTm = {
            1: 60,
            5: 60,
            30: 1440,
            60: 1440,
            1440: 1440
        }
        additional_timaframe = adTm[timeframe]
        print('additional_timaframe', additional_timaframe)
        if not session_name or len(session_name) > 100:
            return jsonify({'message': 'Invalid session name'}), 400
        
        if additional_timaframe < timeframe:
            return jsonify({'message': 'Add timefgrame cant be less then main timeframe'}), 400
        
        coin_essential = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'AAPL', 'EURUSD']
        
        if g.user.payment_status == 'esential' and coin_pair not in coin_essential:
            return jsonify({'message': "Tou have access to 'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'AAPL', 'EURUSD' coin pairs with esential status"}), 400
        tf_essent = [1440, 60]
        tf_premium = [1440, 60, 30]
        tf_premium_plus = [1440, 60, 30, 5, 1]
        if (g.user.payment_status == 'esential' and timeframe not in tf_essent) or  (g.user.payment_status == 'premium' and timeframe not in tf_premium) or (g.user.payment_status == 'premium-plus' and timeframe not in tf_premium_plus):
            return jsonify({'message': 'Not allowed timeframe'}), 400

        balance = 100
        if g.user.payment_status == 'premium':
            balance = 5000
        elif g.user.payment_status == 'premium-plus':
            balance = 5000


        session = Session(user_id=g.user.id, decimal_places=decimal_places, selfdataid=data_id, is_self_data=is_self_data, session_name=session_name, balance=balance, coin_pair=coin_pair, timeframe=timeframe, additional_timaframe=additional_timaframe,  current_PnL=0)
        try:
            db.session.add(session)
            db.session.commit()

            g.user.current_session_id = session.id
            db.session.commit()
        except Exception as e:
            return jsonify({'message': 'An error occurred while adding the session', 'error': str(e)}), 500

        # Преобразование объекта Session в словарь
        session_dict = {
            'id': session.id,
            'user_id': session.user_id,
            'coin_pair': session.coin_pair,
            'timeframe': session.timeframe,
            'additional_timaframe': session.additional_timaframe,
            'session_name': session.session_name,
            'balance': session.balance,
            'is_self_data': is_self_data,
            'current_PnL': session.current_PnL,
            'selfDataId': session.selfdataid,
            'positions': []
        }

        return jsonify({'message': 'Session added successfully', 'session': session_dict}), 201
    except Exception as e:
        print(e)

@api.route('/session/<int:session_id>', methods=['DELETE'])
def delete_session(session_id):

    session = Session.query.get(session_id)
    if not session or session.user_id != g.user.id:
        return jsonify({'message': 'Session not found or not owned by the user'}), 404

    if g.user.sessions.count() <= 1:
        return jsonify({'message': 'Cannot delete the only session'}), 400

    if g.user.current_session_id == session.id:
        previous_session = Session.query.filter(Session.user_id == g.user.id, Session.id < session.id).order_by(Session.id.desc()).first()
        if not previous_session:
            previous_session = Session.query.filter(Session.user_id == g.user.id).order_by(Session.id.desc()).first()
        g.user.current_session_id = previous_session.id
    try:
        Position.query.filter_by(session_id=session.id).delete()
        db.session.delete(session)
        db.session.commit()
    except Exception as e:
        return jsonify({'message': 'An error occurred while deleting the session', 'error': str(e)}), 500

    return jsonify({'message': 'Session deleted successfully', 'current_session': g.user.current_session_id}), 200




@api.route('/add_position/<int:session_id>', methods=['POST'])
def add_position(session_id):
    
    session = Session.query.get(session_id)

    if not session or session.user_id != g.user.id:
        return jsonify({'message': 'Session not found or not owned by the current user'}), 404
    
    g_settings = cache.get('glogal_settings')
    if g_settings is None:
        data_settings = GlobalSettings.query.filter_by(version='v1').first()
        g_settings = data_settings.to_dict()
        cache.set('glogal_settings', g_settings, timeout=120)
    if session.positions.count() >= g_settings['position_in_session']:
        return jsonify({'message': 'You have reached the limit on the number of positions in the session'}), 404


    body = request.get_json()
    data = body.get('position')
    if (not data):
        return jsonify({'message': 'Bed request. No position to save'}), 404
    
    position_user_id = data.get('user_id', 0)

    if g.user.id != position_user_id:
        return jsonify({'message': 'Position does not belong to user'}), 404
    
    position = Position(session_id=session_id, volatility=data.get('volatility'), data_ident=data.get('data_ident'), timeframe=data.get('timeframe'), user_id=position_user_id, stop_loss=data.get('stop_loss', 0), take_profit=data.get('take_profit', 0), coin_pair=data.get('coin_pair', ''), open_price=data.get('open_price', 0), close_price=data.get('close_price', 0), profit=data.get('profit', 0), open_time=data.get('open_time', ''), close_time=data.get('close_time', ''), amount=data.get('amount', 0), target_len=data.get('target_len', 0), type_of_close=data.get('type_of_close', ''), buy_sell=data.get('buy_sell', 'Buy'))
    db.session.add(position)
    db.session.commit()

    return jsonify({'message': 'Position added successfully', 'position_id': position.id}), 200


def jwt_required_and_cache():
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            if g.user.payment_status.lower() not in ['essential', 'premium', 'premium-plus']:
                data = cache.get('cached_init_data')
                if data is not None:
                    response = {'data': data.tolist()}
                if data is None:
                    path = '/app/SERVER_SET/1577836800000_1717113600000.csv'
                    data = asyncio.run(gd.load_data_sets(path))
                    data = data[:200]
                    data = data[data[:, 0].argsort()]
                    cache.set('cached_init_data', data)
                    response = {'data': data.tolist()}
                    return jsonify(response), 200
                else:
                    return jsonify(response), 200

            return f(*args, **kwargs)
        return decorated_function
    return decorator


@api.route('/data', methods=['GET'])
@jwt_required_and_cache()
def get_data():
    @cache.memoize(timeout=120)
    def cached_function(coin, timeframe, finish_date):
        files_map = asyncio.run(gd.get_json_data(coin, timeframe))
        name = ''
        need_find_point = False
        if finish_date == 0:
            name = serv.select_random_file(files_map)
            need_find_point = False
        else:
            name, need_find_point = serv.find_file_containing_timestamp(finish_date, files_map)
        
        if name is None:
            return jsonify({'message': f'Something went wrong, maybe no more data on this pair and timeframe. Try to reload the page to get new chunk of data'}), 402
        
        tm = serv.get_timeframe(timeframe)
        path = f'SERVER_SET/{coin}/{tm}/{name}'
        data = asyncio.run(gd.load_data_sets_s3(path))
        if need_find_point:
            data = data[data[:, 0] > finish_date]
            data = data[data[:, 0].argsort()]
        
        if len(data) > 1000:
            data = data[:1000]
        
        response = {'data': data.tolist()}

        if g.user.payment_status == 'premium-plus' and timeframe != 1440:
            try:
                adTm = {
                    1: 60,
                    5: 60,
                    30: 1440,
                    60: 1440,
                    1440: 1440
                }
                add_timeframe = adTm[timeframe]
                timestamp = finish_date if finish_date != 0 else data[100][0]
                tm_serv = data[100][0] if timestamp == 0 else timestamp
                files_map = asyncio.run(gd.get_json_data(coin, add_timeframe))
                name = serv.find_file_containing_previous_timestamp(tm_serv, files_map)

                tm = serv.get_timeframe(add_timeframe)
                path = f'SERVER_SET/{coin}/{tm}/{name}'
                add_data = asyncio.run(gd.load_data_sets_s3(path))
                if add_timeframe != 1440:
                    index = np.searchsorted(add_data[:, 0], tm_serv)
                    if index < 75:
                        name, need_find_point = serv.find_file_containing_timestamp(add_data[0, 0] - add_timeframe*60*1000, files_map)
                        path = f'SERVER_SET/{coin}/{tm}/{name}'
                        more_data = asyncio.run(gd.load_data_sets_s3(path))
                        more_data = more_data[more_data[:, 0].argsort()]

                        index = np.searchsorted(more_data[:, 0], add_data[0, 0])
                        more_data = more_data[index - 100:]
                        add_data = np.concatenate((more_data, add_data))
                    
                    index = np.searchsorted(add_data[:, 0], tm_serv, side='right')
                    if len(add_data) - index < 75:
                        name, need_find_point = serv.find_file_containing_timestamp(add_data[-1, 0] + add_timeframe*60*1000, files_map)
                        
                        path = f'SERVER_SET/{coin}/{tm}/{name}'
                        more_data = asyncio.run(gd.load_data_sets_s3(path))
                        more_data = more_data[more_data[:, 0].argsort()]

                        index = np.searchsorted(more_data[:, 0], add_data[-1, 0], side='right')
                        more_data = more_data[:index + 100]
                        add_data = np.concatenate((add_data, more_data))

                    print(add_timeframe, tm_serv, data[100][0], len(add_data))
                    add_data = add_data[add_data[:, 0] > tm_serv - 100 * add_timeframe*60*1000]
                    add_data = add_data[add_data[:, 0] < tm_serv + 100 * add_timeframe*60*1000]

                add_data = add_data[add_data[:, 0].argsort()]
                response['add_data'] = add_data.tolist()
            except Exception as e:
                print(e)

        return jsonify(response), 200

    coin = request.args.get('coin')
    timeframe = int(request.args.get('timeframe'))
    finish_date = int(request.args.get('finish_date'))
    return cached_function(coin, timeframe, finish_date)

@api.route('/get_add_data', methods=['GET'])
def get_add_data():
    try:
        timestamp = request.args.get('timestamp')
        coin_pair = request.args.get('coin_pair')
        add_timeframe = request.args.get('add_timeframe')

        if g.user.payment_status == 'premium-plus':
            try:
                adTm = {
                    1: 60,
                    5: 60,
                    30: 1440,
                    60: 1440,
                    1440: 1440
                }

                tm_serv = timestamp
                files_map = asyncio.run(gd.get_json_data(coin_pair, add_timeframe))
                name = serv.find_file_containing_previous_timestamp(tm_serv, files_map)
                tm = serv.get_timeframe(add_timeframe)
                path = f'SERVER_SET/{coin_pair}/{tm}/{name}'
                add_data = asyncio.run(gd.load_data_sets_s3(path))
                # if add_timeframe != 1440:
                index = np.searchsorted(add_data[:, 0], tm_serv)
                if index < 75:
                    name, need_find_point = serv.find_file_containing_timestamp(add_data[0, 0] - add_timeframe*60*1000, files_map)
                    path = f'SERVER_SET/{coin_pair}/{tm}/{name}'
                    more_data = asyncio.run(gd.load_data_sets_s3(path))
                    more_data = more_data[more_data[:, 0].argsort()]

                    index = np.searchsorted(more_data[:, 0], add_data[0, 0])
                    more_data = more_data[index - 100:]
                    add_data = np.concatenate((more_data, add_data))
                
                index = np.searchsorted(add_data[:, 0], tm_serv, side='right')
                if len(add_data) - index < 50:
                    name, need_find_point = serv.find_file_containing_timestamp(add_data[-1, 0] + add_timeframe*60*1000, files_map)
                    
                    path = f'SERVER_SET/{coin_pair}/{tm}/{name}'
                    more_data = asyncio.run(gd.load_data_sets_s3(path))
                    more_data = more_data[more_data[:, 0].argsort()]

                    index = np.searchsorted(more_data[:, 0], add_data[-1, 0], side='right')
                    more_data = more_data[:index + 50]
                    add_data = np.concatenate((add_data, more_data))

                add_data = add_data[add_data[:, 0] > tm_serv - 100 * add_timeframe*60*1000]
                add_data = add_data[add_data[:, 0] < tm_serv + 50 * add_timeframe*60*1000]

                add_data = add_data[add_data[:, 0].argsort()]
                return jsonify(add_data.tolist())
            except Exception as e:
                print(e)

        

    except Exception as e:
        return jsonify({'message': str(e)}), 500

@api.route('/get_position_data', methods=['GET'])
def get_position_data():
    try:
        position_id = request.args.get('position_id')

        position = Position.query.get(position_id)
        if not position:
            return jsonify({'message': 'Position not found'}), 404
        g.position = position
        if position.user_id != g.user.id:
            return jsonify({'message': 'This position does not belong to the user'}), 404
        
        
        @cache.memoize(timeout=7200)
        def cached_function_position(position_id):
            timestamp_open = int(g.position.open_time) * 1000
            timestamp_close = int(g.position.close_time) * 1000
            files_map = asyncio.run(gd.get_json_data(g.position.coin_pair, g.position.timeframe))
            name, need_find_point = serv.find_file_containing_timestamp(timestamp_open, files_map)

            tm = serv.get_timeframe(g.position.timeframe)
            path = f'SERVER_SET/{g.position.coin_pair}/{tm}/{name}'
            data = asyncio.run(gd.load_data_sets_s3(path))
            data = data[data[:, 0] > timestamp_open - 100 * g.position.timeframe*60*1000]
            data = data[data[:, 0].argsort()]
            print('first data len', len(data))
            # Проверяем, есть ли у нас 100 свечей перед timestamp_open
            index = np.searchsorted(data[:, 0], timestamp_open)
            if index < 95:
                # Если свечей недостаточно, загружаем предыдущий файл
                name, need_find_point = serv.find_file_containing_timestamp(data[0, 0] - g.position.timeframe*60*1000, files_map)
                path = f'SERVER_SET/{g.position.coin_pair}/{tm}/{name}'
                more_data = asyncio.run(gd.load_data_sets_s3(path))
                more_data = more_data[more_data[:, 0].argsort()]

                # Находим индекс, чтобы получить 100 свечей перед timestamp_open
                index = np.searchsorted(more_data[:, 0], data[0, 0])
                more_data = more_data[index - 100:]

                # Объединяем старые и новые данные
                data = np.concatenate((more_data, data))

            # Проверяем, есть ли у нас достаточно свечей до timestamp_close
            if data[-1, 0] < timestamp_close:
                # Если свечей недостаточно, загружаем следующий файл
                name, need_find_point = serv.find_file_containing_timestamp(data[-1, 0] + g.position.timeframe*60*1000, files_map)
                path = f'SERVER_SET/{g.position.coin_pair}/{tm}/{name}'
                more_data = asyncio.run(gd.load_data_sets_s3(path))
                more_data = more_data[more_data[:, 0].argsort()]
                print('more data 2', len(more_data))
                # Объединяем старые и новые данные
                data = np.concatenate((data, more_data))

            # Отсекаем данные, которые находятся за пределами нашего интересующего диапазона
            data = data[data[:, 0] >= timestamp_open - 100 * g.position.timeframe*60*1000]
            data = data[data[:, 0] <= timestamp_close]
            print('finish data', len(data))
            return jsonify({'data': data.tolist()}), 200
        
        return cached_function_position(g.position.id)

    except Exception as e:
        return jsonify({'message': str(e)}), 500




@api.route('/upload_screenshot', methods=['POST'])
def upload_screenshot():
    try:
        if 'file' not in request.files:
            return jsonify({'message': 'No file part in the request'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'message': 'No file selected for uploading'}), 400

        bucket = 'charbtmarketdata'
        folder = 'SCREENSHOT_COLLECTION'
        user_id = g.user.id
        payment_status = g.user.payment_status

        # Define upload limits based on user payment status
        upload_limits = {
            'default': 2,
            'essential': 100,
            'premium': 500,
            'premium-plus': 1000
        }

        # Check the number of files already uploaded by the user
        user_files = s3.list_objects_v2(Bucket=bucket, Prefix=f'{folder}/{user_id}/')
        num_files = user_files.get('KeyCount', 0)

        # Check if the user has reached their upload limit
        if num_files >= upload_limits.get(payment_status, 2):
            return jsonify({'message': 'Upload limit reached. Please upgrade your plan to upload more files.'}), 403

        if file:
            filename = secure_filename(file.filename)
            s3_path = f'{folder}/{user_id}/{filename}'

            # Check if the file already exists
            try:
                s3.head_object(Bucket=bucket, Key=s3_path)
                # If the file exists, add a random string to the filename
                filename = f"{filename.rsplit('.', 1)[0]}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}.{filename.rsplit('.', 1)[1]}"
                s3_path = f'{folder}/{user_id}/{filename}'
            except ClientError:
                # If the file does not exist, continue as usual
                pass

            s3.upload_fileobj(file, bucket, s3_path)
            file_url = f"https://{bucket}.s3.amazonaws.com/{s3_path}"
            return jsonify({'message': 'File successfully uploaded', 'file_url': file_url}), 200

        return jsonify({'message': 'Something went wrong'}), 500
    except Exception as e:
        logging.error(e, exc_info=True)
        return jsonify({'message': 'Internal server error'}), 500


@api.route('/get_screenshots', methods=['GET'])
def get_screenshots():
    try:
        bucket = 'charbtmarketdata'
        folder = 'SCREENSHOT_COLLECTION'
        s3_path = f'{folder}/{g.user.id}'

        result = s3.list_objects_v2(Bucket=bucket, Prefix=s3_path)
        if result.get('Contents') is None:
            return jsonify({'result': False, 'urls': []}), 200

        paginator = s3.get_paginator('list_objects_v2')
        urls = []
        for page in paginator.paginate(Bucket=bucket, Prefix=s3_path):
            for obj in page['Contents']:
                relative_path = os.path.relpath(obj['Key'], folder)
                url = f"/{relative_path}"
                last_modified = obj['LastModified']
                urls.append((url, last_modified))

        # Сортировка URL-ов по дате последнего изменения
        urls.sort(key=lambda x: x[1], reverse=True)

        # Возвращение только URL-ов
        urls = [url for url, _ in urls]

        return jsonify({'result': True, 'urls': urls}), 200
    except (BotoCoreError, ClientError) as error:
        return jsonify({'error': str(error)}), 500
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred: ' + str(e)}), 500


@api.route('/delete_screenshot', methods=['DELETE'])
def delete_screenshot():
    try:
        file_url = request.json.get('file_url', None)
        if not file_url:
            return jsonify({'message': 'No file URL provided'}), 400

        bucket = 'charbtmarketdata'
        folder = 'SCREENSHOT_COLLECTION'
        expected_prefix = f"https://{bucket}.s3.amazonaws.com/{folder}/"
        
        if not file_url.startswith(expected_prefix):
            return jsonify({'message': 'Invalid file URL'}), 400
        file_key = file_url[len(f"https://{bucket}.s3.amazonaws.com/"):]
        response = s3.delete_object(Bucket=bucket, Key=file_key)
        return jsonify({'message': 'File successfully deleted'}), 200
    except (BotoCoreError, ClientError) as error:
        logging.error(f"Caught an error: {error}")  # Use logging
        return jsonify({'message': str(error)}), 500
    except Exception as e:
        logging.error(f"Caught an exception: {e}")  # Use logging
        return jsonify({'message': 'An unexpected error occurred: ' + str(e)}), 500


@api.route('/get_session_data', methods=['GET'])
def get_session_data():
    try:
        if not g.user or g.user.payment_status.lower() not in ['premium-plus']:
            return jsonify({'message': 'Allowd only for Premium Plus'}), 404
        
        session_id = request.args.get('session_id')
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'message': 'Session not found'}), 404

        filename = f"session_{session_id}_data.csv"
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            headers = [f"{i}_{j}" for i in range(1, 31) for j in ["time", "open", "high", "low", "close", "volume"]]
            headers.extend(["buy_sell", "profit"])
            writer.writerow(headers)

            for position in session.positions:
                g.position = position
                if position.user_id != g.user.id:
                    continue

                
                timestamp_open = int(g.position.open_time) * 1000
                files_map = asyncio.run(gd.get_json_data(g.position.coin_pair, g.position.timeframe))
                name, need_find_point = serv.find_file_containing_timestamp(timestamp_open, files_map)

                tm = serv.get_timeframe(g.position.timeframe)
                path = f'SERVER_SET/{g.position.coin_pair}/{tm}/{name}'
                data = asyncio.run(gd.load_data_sets_s3(path))
                data = data[data[:, 0] > timestamp_open - 30 * g.position.timeframe*60*1000]
                data = data[data[:, 0] <= timestamp_open]
                data = data[data[:, 0].argsort()]
                print('data: ', len(data))
                # Check if we have enough candles before timestamp_open
                index = np.searchsorted(data[:, 0], timestamp_open)
                print('index: ', index)
                if index < 29:
                    # If not enough candles, load the previous file
                    name, need_find_point = serv.find_file_containing_timestamp(data[0, 0] - g.position.timeframe*60*1000, files_map)
                    path = f'SERVER_SET/{g.position.coin_pair}/{tm}/{name}'
                    more_data = asyncio.run(gd.load_data_sets_s3(path))

                    data = np.concatenate((more_data, data))
                    data = data[data[:, 0] > timestamp_open - 30 * g.position.timeframe*60*1000]
                    data = data[data[:, 0] <= timestamp_open]
                    data = data[data[:, 0].argsort()]
                print('data 2: ', len(data))
                # Add buy_sell and profit columns
                buy_sell = 1 if g.position.buy_sell == 'Buy' else 0
                profit = 1 if g.position.profit > 0 else 0
                row_data = []
                for row in data:
                    row[0] = int(row[0])
                    row_data.extend(row)
                row_data.extend([buy_sell, profit])
                print('row lenth: ', len(row_data))
                writer.writerow(row_data)
        
        @after_this_request
        def remove_file(response):
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception as error:
                    print("Error removing or closing downloaded file handle", error)
            return response

        return send_file(filename, mimetype='text/csv', download_name=filename, as_attachment=True)

    except Exception as e:
        return jsonify({'message': str(e)}), 500
