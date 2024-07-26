from models import User, Settings, GlogalSettings
import logging
import time
from datetime import timedelta
from flask import jsonify, request, jsonify, g
import helpers.email_service as emserv
import uuid
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash, check_password_hash
from __init__ import db, s3, api, cache
import helpers.services as serv
import helpers.logs as lg

@api.route('/change_name', methods=['POST'])
def change_name():
    try:
        data = request.get_json()
        u_id = data.get('id', None)
        new_name = data.get('new_name', None)

        if not u_id or not new_name:
            return jsonify({'message': 'Missing required data'}), 400

        if u_id != g.user.id:
            return jsonify({'message': 'No access'}), 403
        
        if g.user.name_changed >= 3:
            return jsonify({"message": "You can't change name more than 3 times"}), 403
        
        if new_name == g.user.username:
            return jsonify({"message": "New name can't be the same as the old one"}), 400
        old_name = g.user.username
        g.user.username = new_name
        g.user.name_changed += 1
        db.session.commit()

        lg.add_logs(g.client_ip, g.user.id, 5000, f'Changed name from {old_name} to {g.user.username}')
        
        return jsonify({'message': 'Name was changed successfully'}), 200
    except Exception as e:
        return jsonify({'message': 'An error occurred: ' + str(e)}), 500



@api.route('/verify', methods=['GET'])
def verify():
    try:
        details = request.args.get('details', 'user')  # по умолчанию возвращаем только данные пользователя
        user_data = {
            'id': g.user.id,
            'username': g.user.username,
            'email': g.user.email,
            'current_session_id': g.user.current_session_id,
            'settings': g.user.settings.to_dict(),
            'payment_status': g.user.payment_status,
            'refcode': g.user.refcode,
            'name_changed': g.user.name_changed,
            'tokens': g.user.tokens,
            'badge': g.user.badge,
            'registration_date': g.user.registration_date,
            'avatarLink': '' if g.user.avatarLink.split('_')[0] == 'start' else g.user.avatarLink,
            'subscription_to': g.user.subscription_to,
            'blogLastVisit': g.user.blogLastVisit,
        }

        if details in ['sessions', 'all']:
            sessions_data = []
            for session in g.user.sessions:
                session_data = {'id': session.id, 'session_name': session.session_name, 'coin_pair': session.coin_pair, 'timeframe': session.timeframe, 'additional_timaframe': session.additional_timaframe, 'cursor': session.cursor, 'balance': session.balance, 'current_PnL': session.current_PnL, 'positions': []}
                sessions_data.append(session_data)
                if session.id == g.user.current_session_id:
                    positions_data = [{'id': position.id, 'volatility': position.volatility, 'amount': position.amount, 'user_id': position.user_id, 'open_price': position.open_price, 'timeframe': position.timeframe, 'close_price': position.close_price, 'open_time': position.open_time, 'close_time': position.close_time, 'type_of_close': position.type_of_close, 'coin_pair': position.coin_pair, 'profit': position.profit, 'buy_sell': position.buy_sell} for position in session.positions]
                    session_data['positions'] = positions_data if len(positions_data)> 0 else []
                    user_data['current_session'] = session_data
            user_data['sessions'] = sessions_data

        g_settings = cache.get('glogal_settings')
        if g_settings is None:
            data_settings = GlogalSettings.query.filter_by(version='v1').first()
            g_settings = data_settings.to_dict()
            cache.set('glogal_settings', g_settings, timeout=120)
        user_data['global_settings'] = g_settings

        return jsonify(user_data), 200
    except Exception as e:
        logging.error(e, exc_info=True)


@api.route('/set_avatar', methods=['POST'])
def set_avatar():
    
    if g.user.avatarLink:
        try:
            parts = g.user.avatarLink.split('_')
            timestamp = int(parts[1])
            if timestamp + (60*60*24) > time.time():
                return jsonify({'message': 'You can change avatar once in a day'}), 400
        except (IndexError, ValueError):
            return jsonify({'message': 'Error processing avatar timestamp'}), 500
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No file selected for uploading'}), 400

    if file and serv.allowed_file(file.filename):
        if file.content_length > 600 * 1024:
            return jsonify({'message': 'File size must be less than 600KB'}), 400

        filename = f"{uuid.uuid4()}_{int(time.time())}_.{file.filename.rsplit('.', 1)[1].lower()}"
        bucket = 'charbtmarketdata'
        folder = 'AVATARS'
        s3_path = f'{folder}/{filename}'
        try:
            if g.user.avatarLink:
                old_s3_path = g.user.avatarLink.split(f'https://{bucket}.s3.amazonaws.com/')[1]
                s3.delete_object(Bucket=bucket, Key=old_s3_path)

            s3.upload_fileobj(file, bucket, s3_path)
            file_url = f"https://{bucket}.s3.amazonaws.com/{s3_path}"
            g.user.avatarLink = file_url
            db.session.commit()
            lg.add_logs(g.client_ip, g.user.id, 5000, f'Change avatar')
            return jsonify({'message': 'Avatar successfully uploaded'}), 200
        except Exception as e:
            return jsonify({'message': 'Error occurred while uploading file'}), 500
    else:
        return jsonify({'message': 'Invalid file type. Only JPG, GIF, PNG files are allowed.'}), 400
    
@api.route('/delete_avatar', methods=['DELETE'])
def delete_avatar():
    try:
        bucket = 'charbtmarketdata'
        # Если у пользователя есть аватар, удалите его
        if g.user.avatarLink:
            s3_path = g.user.avatarLink.split(f'https://{bucket}.s3.amazonaws.com/')[1]
            s3.delete_object(Bucket=bucket, Key=s3_path)
            g.user.avatarLink = f'start_{int(time.time())}_fin'
            db.session.commit()
            lg.add_logs(g.client_ip, g.user.id, 5000, f'Delete avatar')
            return jsonify({'message': 'Avatar successfully deleted'}), 200
        else:
            return jsonify({'message': 'No avatar to delete'}), 400

    except Exception as e:
        return jsonify({'message': 'An error occurred while deleting the avatar', 'error': str(e)}), 500
    
@api.route('/delete_account', methods=['DELETE'])
def delete_account():
    try:
        if g.user.payment_status != 'default' and g.user.subscription_to == 0:
            return jsonify({'message': 'You must cancel your subscription and wait until the end of the paid period to delete account'}), 200
        
        g.user.delete_account = True
        db.session.commit()
        lg.add_logs(g.client_ip, g.user.id, 1000, f'Delete account')
        return jsonify({'message': 'Account will be deleted in 30 days'}), 200
        
    except Exception as e:
        return jsonify({'message': 'An error occurred while deleting the account', 'error': str(e)}), 500



@api.route('/change_email', methods=['POST'])
def change_email():
    try:
        data = request.get_json()
        new_email = data.get('new_email')
        password = data.get('password')

        if User.query.filter_by(email=new_email).first():
            return jsonify({'message': 'Email already in use'}), 400

        if not new_email or not password:
            return jsonify({'message': 'Email and password are required'}), 400

        if not check_password_hash(g.user.password_hash, password):
            return jsonify({'message': 'Invalid password'}), 401

        g.user.change_email = new_email

        expires = timedelta(days=3)
        token = create_access_token(identity=g.user.id, expires_delta=expires)
        g.user.token = token
        db.session.commit()

        link = f'http://localhost:5000/api/email_confirm?token={token}'
        emserv.send_email(new_email, 'service@charbt.com', 'Email Confirmation', link)

        lg.add_logs(g.client_ip, g.user.id, 5000, f'Change email request')

        return jsonify({'message': 'Confirm your new email and log in'}), 200

    except Exception as e:
        return jsonify({'message': 'An error occurred while changing the email', 'error': str(e)}), 500


@api.route('/change_password', methods=['POST'])
def change_password():
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not current_password or not new_password:
            return jsonify({'message': 'Current and new password are required'}), 400

        if not check_password_hash(g.user.password_hash, current_password):
            return jsonify({'message': 'Invalid current password'}), 401

        g.user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        lg.add_logs(g.client_ip, g.user.id, 5000, f'Password successfully changed')

        return jsonify({'message': 'Password successfully changed'}), 200

    except Exception as e:
        return jsonify({'message': 'An error occurred while changing the password', 'error': str(e)}), 500


@api.route('/create_ticket', methods=['POST'])
def create_ticket():
    try:        
        if g.user.lastTiket:
            try:
                last_request =  int(g.user.lastTiket.split('_')[1])
                if last_request + (60*60*24) > time.time():
                    return jsonify({'message': 'You can send tiket once in a 24 hours'}), 400
            except Exception as e:
                return jsonify({'message': 'An error occurred while decoding timestamp: {}'.format(e)}), 500

        data = request.get_json()
        subject = data.get('subject')
        message = data.get('message')

        ticketId = f'{str(uuid.uuid4())[:8]}_{int(time.time())}'
        g.user.lastTiket = ticketId
        db.session.commit()
        # Отправка письма

        emserv.send_tiket('support@charbt.com', 'service@charbt.com', f'{subject}#{ticketId}', message, str(g.user.id), str(g.user.email))
        emserv.tiket_created(g.user.email, 'support@charbt.com', ticketId)
        
        lg.add_logs(g.client_ip, g.user.id, 5000, f'Tiket was created')

        return jsonify({'message': 'Your ticket has been successfully created. You will receive a response from our team to the email to which your account is registered.'}), 200
    except Exception as e:
        return jsonify({'message': 'An error occurred while creating your ticket: {}'.format(e)}), 500
    
@api.route('/set_settings', methods=['POST'])
def set_settings():
    data = request.get_json()
    new_settings = data.get('settings', None)
    if new_settings is not None:
        validation = {
            'rightScale': [True, False],
            'theme': ['dark', 'light']
        }

        settings = Settings.query.get(g.user.settings_id)
        if settings is None:
            return jsonify({'message': 'Settings not found'}), 404
        for key, val in new_settings.items():
            if hasattr(settings, key):
                if key in validation and val not in validation[key]:
                    return jsonify({'message': f'Invalid value for {key}'}), 400
                setattr(settings, key, val)
        db.session.commit()
        return jsonify({'message': 'Settings updated successfully'}), 200
    return jsonify({'message': 'No settings provided'}), 400


            

