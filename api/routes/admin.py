from models import User, BlackList, PaymentPlans, TextDb, Logs, Admin, AllowedIp, BlogPost, Poll, PollOption, Vote, GlobalSettings
from datetime import datetime, timedelta, timezone
import time
from flask import redirect, request, g, url_for, flash, jsonify
from botocore.exceptions import ClientError
import helpers.email_service as emserv
from flask_jwt_extended import create_access_token, set_access_cookies
from werkzeug.security import generate_password_hash, check_password_hash
from __init__ import db, s3, adm
from werkzeug.utils import secure_filename
from flask import request, render_template, redirect, make_response
from flask_jwt_extended import create_access_token
from werkzeug.security import check_password_hash
import uuid

@adm.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = Admin.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            sessionCode = str(uuid.uuid4())[:8]
            identity = {'user_id': user.id, 'session_code': sessionCode}
            access_token = create_access_token(identity=identity, expires_delta=timedelta(seconds=3600))
            flash('You were successfully logged in')
            resp = make_response(redirect(url_for('adm.home')))
            # resp.set_cookie('access_token_cookie', access_token)
            set_access_cookies(resp, access_token)
            user.sessionCode = sessionCode
            db.session.commit()
            return resp

        return "Invalid username or password", 401

    return render_template('admin/login.html')

@adm.route('/home')
def home():
    return render_template('admin/home.html')


@adm.route('/logs', methods=['GET', 'POST'])
def logs():
    filter_action_code = request.form.get('action_code')
    filter_user_id = request.form.get('user_id')
    filter_ip_address = request.form.get('ip_address')

    query = Logs.query

    if filter_action_code:
        query = query.filter(Logs.action_code == filter_action_code)
    if filter_user_id:
        query = query.filter(Logs.user_id == filter_user_id)
    if filter_ip_address:
        query = query.filter(Logs.ip_address == filter_ip_address)

    logs = query.order_by(Logs.timestamp.desc()).all()

    return render_template('admin/logs.html', logs=logs)


@adm.route('/statistic')
def statistic():
    return render_template('admin/statistic.html')

@adm.route('/users')
def users():
    return render_template('admin/users.html')

from flask import request, render_template, redirect, url_for
from werkzeug.security import generate_password_hash

@adm.route('/user_search', methods=['POST'])
def user_search():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        email = request.form.get('email')
        refcode = request.form.get('refcode')
        
        error_message = None
        user = None
        if user_id:
            user = User.query.get(user_id)
        elif email:
            user = User.query.filter_by(email=email).first()
        elif refcode:
            user = User.query.filter_by(refcode=refcode).first()

        if user:
            return redirect(url_for('adm.user_edit', user_id=user.id))
        else:
            error_message = "User not found"
    return render_template('admin/users.html', error_message=error_message)

@adm.route('/user_edit/<int:user_id>', methods=['GET', 'POST'])
def user_edit(user_id):
    user = User.query.get(user_id)
    if not user:
        return "User not found", 404

    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.refcode = request.form.get('refcode')
        user.myrefer = request.form.get('myrefer')
        user.email_confirmed = bool(request.form.get('email_confirmed'))
        user.password_hash = generate_password_hash(request.form.get('password'))
        user.tokens = int(request.form.get('tokens'))
        user.name_changed = int(request.form.get('name_changed'))
        user.avatarLink = request.form.get('avatarLink')
        user.token = request.form.get('token')
        user.settings_id = int(request.form.get('settings_id'))
        user.payment_status = request.form.get('payment_status')
        user.subscription_to = int(request.form.get('subscription_to'))
        user.subscription_id = request.form.get('subscription_id')
        user.current_session_id = int(request.form.get('current_session_id'))

        db.session.commit()

        return redirect(url_for('adm.user_edit', user_id=user.id))

    return render_template('admin/user_edit.html', user=user)

@adm.route('/delete_old_logs', methods=['POST'])
def delete_old_logs():
    days = request.form.get('days')
    if not days.isdigit():
        flash('Number of days must be a number.')
        return redirect(url_for('adm.logs'))

    days = int(days)
    cutoff_time = datetime.now() - timedelta(days=days)

    try:
        num_rows_deleted = db.session.query(Logs).filter(Logs.timestamp < cutoff_time).delete()
        db.session.commit()
        flash(f'Successfully deleted {num_rows_deleted} log entries.')
    except Exception as e:
        flash('An error occurred while trying to delete log entries.')

    return redirect(url_for('adm.logs'))


@adm.route('/logout')
def logout():
    resp = make_response(redirect(url_for('adm.login')))
    resp.set_cookie('access_token_cookie', '', expires=0)
    return resp

@adm.route('/send_email', methods=['POST'])
def send_email():
    user_email = request.form.get('email')
    message = request.form.get('message')
    service_email = request.form.get('service_email')

    emserv.send_servce_info_msg(user_email, service_email, message)
    
    user = User.query.filter_by(email=user_email).first()

    if user:
        return redirect(url_for('adm.user_edit', user_id=user.id))
    else:
        flash('User not found')
        return redirect(url_for('adm.user_search'))

@adm.route('/settings', methods=['POST', 'GET'])
def settings():
    if request.method == 'POST':
        ip = request.form.get('ip')
        action = request.form.get('action')

        if action == 'Add':
            # Создайте новый объект AllowedIp и добавьте его в базу данных
            new_ip = AllowedIp(ip=ip, user_id=g.admin.id)
            db.session.add(new_ip)
        elif action == 'Remove':
            # Найдите объект AllowedIp в базе данных и удалите его
            ip_to_remove = AllowedIp.query.filter_by(ip=ip).first()
            if ip_to_remove:
                db.session.delete(ip_to_remove)

        # Сохраните изменения в базе данных
        db.session.commit()
    print('g.admin.allowed_ip:', g.admin.allowed_ip)
    ips = g.admin.allowed_ip
    return render_template('admin/settings.html', allowed_ips=ips)

@adm.route('/black_list', methods=['GET', 'POST'])
def black_list():
    if request.method == 'POST':
        if 'add' in request.form:
            ip = request.form.get('ip')
            to = datetime.strptime(request.form.get('to'), '%Y-%m-%d')
            reason = request.form.get('reason')
            new_entry = BlackList(ip=ip, to=to, reason=reason)
            db.session.add(new_entry)
            db.session.commit()
        elif 'delete' in request.form:
            id = request.form.get('id')
            BlackList.query.filter_by(id=id).delete()
            db.session.commit()
    black_list = BlackList.query.all()
    return render_template('admin/black_list.html', black_list=black_list)

from flask import request

@adm.route('/payment_plans', methods=['GET', 'POST'])
def payment_plans():
    if request.method == 'POST':
        plan_id = request.form.get('plan_id')
        plan = PaymentPlans.query.get(plan_id)
        if plan:
            plan.name = request.form.get('name')
            plan.token_price_day = int(request.form.get('token_price_day'))
            plan.price_subscription_month_1 = float(request.form.get('price_subscription_month_1'))
            plan.price_subscription_year_1 = float(request.form.get('price_subscription_year_1'))
            plan.price_subscription_month_2 = float(request.form.get('price_subscription_month_2'))
            plan.price_subscription_year_2 = float(request.form.get('price_subscription_year_2'))
            plan.price_id_month = request.form.get('price_id_month')
            plan.price_id_annualy = request.form.get('price_id_annualy')

            for access in plan.access:
                access.name = request.form.get(f'access_name_{access.id}')
                access.description = request.form.get(f'description_{access.id}')
                access.number = int(request.form.get(f'number_{access.id}'))
                access.all = int(request.form.get(f'all_{access.id}'))
                access.on = bool(request.form.get(f'on_{access.id}'))

            db.session.commit()

    payment_plans = PaymentPlans.query.all()
    return render_template('admin/plans.html', payment_plans=payment_plans)


@adm.route('/text_db', methods=['GET', 'POST'])
def text_db():
    if request.method == 'POST':
        text_id = request.form.get('text_id')
        text_db = TextDb.query.get(text_id)
        if text_db:
            text_db.name_id = request.form.get('name_id')
            text_db.name = request.form.get('name')
            text_db.text = request.form.get('text')
            db.session.commit()
    text_db_entries = TextDb.query.all()
    return render_template('admin/texts.html', text_db_entries=text_db_entries)

@adm.route('/delete_user', methods=['POST'])
def delete_user():
    id = int(request.form.get('id', 0))
    username = request.form.get('username')
    print(id, username)
    user = User.query.get(id)
    if user:
        if username == user.username:
            bucket = 'charbtmarketdata'
            # Если у пользователя есть аватар, удалите его
            if user.avatarLink:
                if f'https://{bucket}.s3.amazonaws.com/' in user.avatarLink:
                    s3_path = user.avatarLink.split(f'https://{bucket}.s3.amazonaws.com/')[1]
                    s3.delete_object(Bucket=bucket, Key=s3_path)
                    user.avatarLink = f'start_{int(time.time())}_fin'
                    db.session.commit()
                
            folder = 'SCREENSHOT_COLLECTION'
            s3_path = f'{folder}/{user.id}'

            try:
                objects = s3.list_objects_v2(Bucket=bucket, Prefix=s3_path)
                for obj in objects.get('Contents', []):
                    s3.delete_object(Bucket=bucket, Key=obj['Key'])
            except ClientError as e:
                print(f"Error: {e}")

            db.session.delete(user)
            db.session.commit()

    return redirect(url_for('adm.users'))

@adm.route('/blog', methods=['GET', 'POST'])
def blog():
    if request.method == 'POST':
        # Logic for creating a new post
        title = request.form.get('title')
        content = request.form.get('content')
        print(title, content)

        # Logic for uploading an image to S3 and saving its URL
        file = request.files['file']
        filename = secure_filename(file.filename)
        bucket = 'charbtmarketdata'
        folder = 'BLOG_IMG'
        s3_path = f'{folder}/{filename}'
        s3.upload_fileobj(file, bucket, s3_path)
        img_url = f"https://{bucket}.s3.amazonaws.com/{s3_path}"
        
        comments_on = 'comments_on' in request.form
        new_post = BlogPost(title=title, content=content, user_id=1, img_url=img_url, comments_on=comments_on)
        db.session.add(new_post)
        db.session.commit()

        # Logic for creating a new poll and options
        question = request.form.get('question')
        options = request.form.getlist('options')
        disabled = 'disabled' in request.form
        to_date = request.form.get('to_date')

        # Check if question and options are provided
        if question and options:
            new_poll = Poll(question=question, blog_post_id=new_post.id, disabled=disabled, to_date=to_date)
            db.session.add(new_poll)
            db.session.commit()

            for option in options:
                new_option = PollOption(name=option, poll=new_poll)
                db.session.add(new_option)
            db.session.commit()

        settings = GlobalSettings.query.filter_by(version='v1').first()
        settings.blogLastPost = datetime.now(timezone.utc)
        db.session.commit()

    posts = BlogPost.query.all()
    return render_template('admin/blog.html', posts=posts)



@adm.route('/update_blog', methods=['GET', 'POST'])
def update_blog():
    if request.method == 'POST':
        post_id = request.form.get('post_id')
        post = BlogPost.query.get(post_id)
        if 'delete' in request.form:
            if post.img_url:
                bucket = 'charbtmarketdata'
                old_s3_path = post.img_url.split(f'https://{bucket}.s3.amazonaws.com/')[1]
                s3.delete_object(Bucket=bucket, Key=old_s3_path)
            # Удаление связанного опроса, вариантов ответов и голосов
            if post.poll:
                for option in post.poll.options:
                    for vote in option.votes:
                        db.session.delete(vote)
                    db.session.delete(option)
                db.session.delete(post.poll)
            # Удаление связанных комментариев
            for comment in post.comments:
                db.session.delete(comment)
            db.session.delete(post)
            db.session.commit()

            return redirect(url_for('adm.update_blog'))
        else:
            post.title = request.form.get('title')
            post.content = request.form.get('content')
            post.comments_on = 'comments_on' in request.form
            file = request.files['file']
            if file:
                if post.img_url:
                    bucket = 'charbtmarketdata'
                    old_s3_path = post.img_url.split(f'https://{bucket}.s3.amazonaws.com/')[1]
                    s3.delete_object(Bucket=bucket, Key=old_s3_path)
                filename = secure_filename(file.filename)
                bucket = 'charbtmarketdata'
                folder = 'BLOG_IMG'
                s3_path = f'{folder}/{filename}'
                s3.upload_fileobj(file, bucket, s3_path)
                post.img_url = f"https://{bucket}.s3.amazonaws.com/{s3_path}"
            if post.poll:
                post.poll.disabled = 'disabled' in request.form
                post.poll.rewardPaid = 'rewardPaid' in request.form
                post.poll.to_date = datetime.fromisoformat(request.form.get('to_date'))
            db.session.commit()
            return redirect(url_for('adm.update_blog'))
    else:

        posts = BlogPost.query.all()
        return render_template('admin/blog_upd.html', posts=posts)
    

@adm.route('/add_vote', methods=['POST'])
def add_vote():
    poll_option_id = request.form.get('option_id')
    user_id = 1  # Замените на ID текущего пользователя
    vote = Vote(user_id=user_id, poll_option_id=poll_option_id)
    db.session.add(vote)
    db.session.commit()
    return redirect(url_for('adm.update_blog'))

@adm.route('/reward', methods=['POST'])
def reward():
    try:
        poll_id = request.form.get('poll_id')
        correct_option_id = request.form.get('correct_option_id')

        poll = Poll.query.get(poll_id)
        correct_option = PollOption.query.get(correct_option_id)

        if not poll or not correct_option or correct_option.poll_id != poll.id:
            return jsonify({'message': 'Invalid pollId or correctOptionId'}), 400

        for vote in correct_option.votes:
            user = User.query.get(vote.user_id)
            user.tokens += 1
        
        poll.rewardPaid = True

        db.session.commit()

        return redirect(url_for('adm.update_blog'))
    except Exception as e:
        print(jsonify({'Message': e}))
        return make_response(jsonify({'Message': e}), 500)


from flask import render_template, request, redirect, url_for

@adm.route('/global_settings', methods=['GET', 'POST'])
def global_settings():
    if request.method == 'POST':
        global_settings = GlobalSettings.query.filter_by(version='v1').first()
        global_settings.version = request.form.get('version')
        global_settings.blogLastPost = request.form.get('blogLastPost')
        global_settings.blogOn = request.form.get('blogOn') == 'on'
        global_settings.startTheme = request.form.get('startTheme')
        db.session.commit()
        return redirect(url_for('adm.global_settings'))
    else:
        global_settings = GlobalSettings.query.filter_by(version='v1').first()
        return render_template('admin/global_settings.html', global_settings=global_settings)
