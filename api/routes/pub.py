from models import User, Session, PaymentPlans, TextDb, Settings, BlogPost, GlobalSettings, BlackList
import logging
from decouple import config
import time
import stripe
import helpers.tel as tel
from datetime import timedelta
import asyncio
from flask import jsonify, redirect, request, jsonify, abort, g, make_response, after_this_request
import helpers.email_service as emserv
import uuid
from functools import wraps
from flask_jwt_extended import create_access_token, decode_token
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import BadRequest
from __init__ import db, cache, pub, executor
import helpers.services as serv
import helpers.logs as lg
from datetime import datetime
import json

@pub.route('/get_global_settings', methods=['GET'])
@cache.memoize(timeout=120)  # кешируем результат на 1 час
def get_global_settings():
    settings = GlobalSettings.query.filter_by(version='v1').first()
    if settings is not None:
        return jsonify(settings.to_dict())
    else:
        return jsonify({"error": "No settings found"}), 404
    
def check_ip_in_blacklist(ip):
    blacklist = BlackList.query.filter_by(ip=ip).first()
    if blacklist and blacklist.to >= datetime.now():
        return True, jsonify({'message': 'Your IP is banned until ' + blacklist.to.strftime('%Y-%m-%d %H:%M:%S')}), 403
    return False, None, None


@pub.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({'data': 'Invalid email or password'}), 401
        if not user.email_confirmed:
            return jsonify({'data': 'Please confirm your email'}), 202

        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        is_banned, response, status_code = check_ip_in_blacklist(client_ip)
        if is_banned:
            return response, status_code
        
        clients_ips = json.loads(user.ip_list)
        if client_ip not in clients_ips:
            if len(clients_ips)< 6:
                clients_ips.append(client_ip)
            else:
                clients_ips.pop(0)
                clients_ips.append(client_ip)

            user.ip_list = json.dumps(clients_ips)

        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'current_session_id': user.current_session_id,
            'settings': user.settings.to_dict(),
            'payment_status': user.payment_status,
            'refcode': user.refcode,
            'name_changed': user.name_changed,
            'registration_date': user.registration_date,
            'tokens': user.tokens,
            'badge': user.badge,
            'data_size': user.data_size,
            'avatarLink': '' if user.avatarLink.split('_')[0] == 'start' else user.avatarLink,
            'subscription_to': user.subscription_to,
            'blogLastVisit': user.blogLastVisit,
        }

        expires = timedelta(days=10)
        sessionCode = str(uuid.uuid4())[:8]
        identity = {'user_id': user.id, 'session_code': sessionCode}
        token = create_access_token(identity=identity, expires_delta=expires)

        user.sessionCode = sessionCode
        user.login_ip = client_ip
        db.session.commit()

        lg.add_logs(client_ip, user.id, 1000, 'login')

        return jsonify({'jwt': token, 'data': user_data}), 200
    except Exception as e:
        logging.error("Exception occurred", exc_info=True)
        return jsonify({'message': 'An error occurred'}), 500
    
@pub.route('/user_exists', methods=['POST'])
def user_exists():

    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'message': 'Missing email parameter'}), 400

    user = User.query.filter_by(email=email).first()

    if user:
        return jsonify({'exist': True}), 200
    else:
        return jsonify({'exist': False}), 404

@pub.route('/register', methods=['POST'])
def register():
    
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    refcode = data.get('ref', '')

    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email already exists'}), 400
    
    client_ip = request.remote_addr
    list_of_ip = [client_ip]
    ser_ip = json.dumps(list_of_ip)
    tokens = 0
    if refcode != '':
        referer = User.query.filter_by(refcode=refcode).first()
        if referer:
            tokens += 10

    user = User(email=email, myrefer=refcode, tokens=tokens, ip_list=ser_ip, username=username, password_hash=generate_password_hash(password), payment_status='default', settings=Settings())
    db.session.add(user)
    db.session.commit()

    session = Session(user_id=user.id, coin_pair='BTCUSDT', timeframe=1440, session_name=serv.random_string().upper(), balance=500, current_PnL=0)
    db.session.add(session)
    db.session.commit()
    user.current_session_id = session.id
    db.session.commit()

    expires = timedelta(days=3)
    token = create_access_token(identity=user.id, expires_delta=expires)
    user.token = token
    db.session.commit()

    env = config('ENV')
    link = 'serv.charbt.com' if env == 'production' else 'localhost:5000'
    https = 'https' if env == 'production' else 'http'

    link = f'{https}://{link}/pub/email_confirm?token={token}'
    emserv.send_email(user.email, 'service@charbt.com', 'Email Confirmation', link)

    return jsonify({'message': 'Registered successfully'}), 201

@pub.route('/email_confirm', methods=['GET'])
def confirm_email():
    token = request.args.get('token')
    
    if not token:
        return jsonify({'message': 'Token is missing'}), 400

    try:
        decoded_token = decode_token(token)
        print(decoded_token)
        user_id = int(decoded_token['sub'])
        logging.info(f'token: {decoded_token}')
        logging.info(f'id: {user_id}')
    except Exception as e:
        logging.error(f'Error decoding token: {e}')
        return jsonify({'message': 'Invalid or expired token'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    user.email_confirmed = True
    if user.change_email:
        user.email = user.change_email
        user.change_email = ''
    db.session.commit()

    env = config('ENV')
    link = 'charbt.com' if env == 'production' else 'localhost:3000'
    https = 'https' if env == 'production' else 'http'

    msg = f'✔ New user registred. {user.username}, {user.email}'

    @after_this_request
    def send_telegram_notification(response):
        executor.submit(asyncio.run, tel.send_inform_message(msg, '', False))
        return response

    return redirect(f"{https}://{link}/login?emailVerified=true")

@pub.route('/get_text', methods=['GET'])
def get_text():
    name_id = request.args.get('name_id')

    if not name_id:
        raise BadRequest('name_id parameter is required')

    text = cache.get(name_id)
    if text is not None:
        return jsonify({'data': text}), 200

    data = TextDb.query.filter_by(name_id=name_id).first()

    if not data:
        abort(404, description="Resource not found")

    text = {
        'date': data.date,
        'name': data.name,
        'text': data.text
    }

    cache.set(name_id, text, timeout=120)
    return jsonify({'data': text}), 200

@pub.route('/payment_plans', methods=['GET'])
def get_payment_plans():
    cached_payment_plans = cache.get('cached_payment_plans')
    if cached_payment_plans:
        return jsonify(cached_payment_plans), 200

    try:
        payment_plans = PaymentPlans.query.all()
        payment_plans_dict = {plan.name: plan.to_dict() for plan in payment_plans}
        cache.set('cached_payment_plans', payment_plans_dict, timeout=120)
        return jsonify(payment_plans_dict), 200
    except Exception as e:
        logging.info(e)
        return jsonify(error=str(e)), 500
    

@pub.route('/request_reset_password', methods=['POST'])
def request_reset_password():
    data = request.get_json()
    email = data.get('email')

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'Cannot find the provided email'}), 202

    expires = timedelta(hours=24)
    reset_token = create_access_token(identity=user.id, expires_delta=expires)

    link = f'http://localhost:3000/reset_password?token={reset_token}'
    emserv.send_email(user.email, 'service@charbt.com', 'Password Recovery', link)
    lg.add_logs(g.client_ip, user.id, 2000, f'Request reset password')

    return jsonify({'message': 'Please check your email for a password reset link'}), 200


@pub.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    reset_token = data.get('token')
    new_password = data.get('new_password')

    if not reset_token or not new_password:
        return jsonify({'message': 'Missing token or new_password parameter'}), 400

    try:
        decoded_token = decode_token(reset_token)
        user_id = int(decoded_token['sub'])
    except Exception as e:
        logging.error(f'Error decoding token: {e}')
        return jsonify({'message': 'Invalid or expired token'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    lg.add_logs(g.client_ip, user.id, 2000, f'Password was reset')

    return jsonify({'message': 'Password has been reset successfully'}), 200

@pub.route('/sub_deleted', methods=['POST'])
def stripe_webhook_delete():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    try:
        stripe.api_key = config('STRIPE_SECRET')
        endpoint_secret = config('STRIPE_ENDPOINT_DELETED')
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return 'Invalid signature', 400

    # Handle the event
    if event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription['customer']

        # Fetch the customer
        customer = stripe.Customer.retrieve(customer_id)

        user = User.query.filter_by(email=customer.email).first()
        print('user.id', user.id)
        if user:
            # Update user status in the database
            user.payment_status = 'default'
            user.subscription_id = ''
            user.subscription_to = time.time()
            db.session.commit()

            lg.add_logs(g.client_ip, user.id, 3000, f'Subscription deleted Sub_id: {user.subscription_id}')
        
    return 'Success', 200

@pub.route('/sub_canceled', methods=['POST'])
def stripe_webhook_cancel():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    try:
        stripe.api_key = config('STRIPE_SECRET')
        endpoint_secret = config('STRIPE_ENDPOINT_CANCELED')
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return 'Invalid signature', 400

    # Handle the event
    if event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        customer_id = subscription['customer']

        if subscription['cancel_at_period_end']:

            product_id = subscription['items']['data'][0]['price']['product']
            product = stripe.Product.retrieve(product_id)

            # Get the plan name
            plan = product['name']
            # Fetch the customer
            customer = stripe.Customer.retrieve(customer_id)

            user = User.query.filter_by(email=customer.email).first()
            if user:
                emserv.send_email_sub_confirm(user.email, 'payment@charbt.com', 'Subscription Cancelled', user.username, plan, subscription['id'])
            
            lg.add_logs(g.client_ip, user.id, 3000, f'Subscription canceled Sub_id: {user.subscription_id}')

    return 'Success', 200


@pub.route('/sub_complite', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    try:
        stripe.api_key = config('STRIPE_SECRET')
        endpoint_secret = config('STRIPE_ENDPOINT_COMPLITE')
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return 'Invalid signature', 400
    # Handle the event
    if event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        customer_id = subscription['customer']

        # Fetch the customer
        customer = stripe.Customer.retrieve(customer_id)
        # Fetch the price and product
        price_id = subscription['items']['data'][0]['price']['id']
        price = stripe.Price.retrieve(price_id)
        product = stripe.Product.retrieve(price['product'])
        user = User.query.filter_by(email=customer.email).first()
        if user:
            # Update user status in the database
            user.payment_status = product.name.lower()
            user.subscription_to = 0
            if '_' in product.name:
                user.payment_status = product.name.split('_')[0].lower()
                if product.name.split('_')[1].lower() == 'annualy':
                    user.badge = 'green'
            user.subscription_id = subscription['id']
            db.session.commit()
            if user.myrefer != '':
                refer = User.query.filter_by(refcode=user.myrefer).first()
                if refer:
                    refer.tokens = refer.tokens+10
                    db.session.commit()

            emserv.send_email_sub_confirm(user.email, 'payment@charbt.com', 'Payment Confirmation', user.username, product.name, subscription['id'])
            lg.add_logs(g.client_ip, user.id, 3000, f'Subscription complite Sub_id: {subscription["id"]}')

    return 'Success', 200

@pub.route('/blog_posts', methods=['GET'])
def get_blog_posts():
    try:
        blog_data = cache.get('blog_data')
        if blog_data is not None:
            return jsonify(blog_data), 200
        posts = BlogPost.query.all()
        blog_data = []
        for post in posts:
            post_dict = post.to_dict()
            post_dict['isVoted'] = True
            if post_dict['poll']:
                for option in post_dict['poll']['options']:
                    option['votes'] = len(option['votes'])
            blog_data.append(post_dict)
        cache.set('blog_data', blog_data, timeout=120)
        return jsonify(blog_data), 200
    except Exception as e:
        return make_response(jsonify({'Message': e}), 500)