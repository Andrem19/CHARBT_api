from models import User, PaymentPlans
import logging
from decouple import config
import stripe
import helpers.logs as lg
import time
from datetime import datetime
from sqlalchemy import func
from flask import jsonify, request, jsonify, g
from __init__ import db, api

@api.route('/tokens_subscription', methods=['POST'])
def purchase_plan():
    if g.user.payment_status != 'default':
        return jsonify({'message': 'You can buy tokens subscription only if you have default status'}), 404

    data = request.get_json()
    plan = data.get('plan')
    days = data.get('days')

    if not plan or not days:
        return jsonify({'message': 'Plan and days are required'}), 400


    plan_inst = PaymentPlans.query.filter(func.upper(PaymentPlans.name) == plan.upper()).first()

    if not plan_inst:
        return jsonify({'message': 'Not existing plan'}), 404

    price = plan_inst.token_price_day * days

    if not isinstance(price, (int, float)):
        return jsonify({'message': 'Price calculation error'}), 500

    if g.user.tokens < price:
        return jsonify({'message': 'Not enough tokens'}), 404
    
    g.user.payment_status = plan_inst.name.lower()
    g.user.subscription_to = time.time() + (days * 86400)
    g.user.tokens -= price
    db.session.commit()

    lg.add_logs(g.client_ip, g.user.id, 7000, f'Token subscription Price: {price} Plan: {plan_inst.name} Days: {days}')

    return jsonify({'message': 'Subscription purchased successfully'}), 200

@api.route('/transfer_tokens', methods=['POST'])
def transfer_tokens():
    data = request.get_json()
    tokens = data.get('tokens')
    refcode = data.get('refcode')

    if not tokens or not refcode:
        return jsonify({'message': 'Tokens and refcode are required'}), 400

    if not isinstance(tokens, int) or tokens <= 0:
        return jsonify({'message': 'Tokens must be a positive integer'}), 400

    if g.user.tokens < tokens:
        return jsonify({'message': 'Not enough tokens'}), 404

    receiver = User.query.filter_by(refcode=refcode).first()

    if not receiver:
        return jsonify({'message': 'Receiver not found'}), 404

    g.user.tokens -= tokens
    receiver.tokens += tokens

    try:
        db.session.commit()
    except Exception as e:
        return jsonify({'message': 'Database error: {}'.format(str(e))}), 500

    lg.add_logs(g.client_ip, g.user.id, 7000, f'Token subscription Sender: {g.user.id} Receiver: {receiver.id} Tokens: {tokens}')

    return jsonify({'message': 'Tokens transferred successfully'}), 200
    

@api.route('/checkout', methods=['POST'])
def checkout():
    try:
        stripe.api_key = config('STRIPE_SECRET')

        payment_data = request.get_json()

        if 'token' not in payment_data or 'type' not in payment_data or 'plan' not in payment_data:
            return jsonify({'message': 'Invalid input'}), 202

        planInstance = PaymentPlans.query.filter_by(name=payment_data['plan']).first()
        if not planInstance:
            return jsonify({'message': 'Plan is undefined'}), 202
        
        plan = ''
        amount = 0

        if payment_data['type'] == 'monthly':
            plan = planInstance.price_id_month
            amount = int(planInstance.price_subscription_month_1 * 100)  # Учитываем сумму из плана подписки
        elif payment_data['type'] == 'annualy':
            plan = planInstance.price_id_annualy
            amount = int(planInstance.price_subscription_year_1 * 100)  # Учитываем сумму из плана подписки
        else:
            return jsonify({'message': 'Plan is undefined'}), 202

        customer = stripe.Customer.create(
            email=g.user.email,
        )

        payment_method = stripe.PaymentMethod.create(
            type='card',
            card={
                'token': payment_data['token']
            }
        )
        stripe.PaymentMethod.attach(
            payment_method.id,
            customer=customer.id,
        )
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='usd',
            customer=customer.id,
            payment_method=payment_method.id,
            setup_future_usage='off_session'
        )
        print('payment_intent', payment_intent)
        if not payment_intent:
            return jsonify({'message': 'PaymentIntent creation failed'}), 202

        return jsonify({'message': 'PaymentIntent created', 'client_secret': payment_intent.client_secret, 'payment_intent_id': payment_intent.id, 'customer_id': customer.id, 'plan': plan}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 400

@api.route('/create-subscription', methods=['POST'])
def create_subscription():
    try:
        stripe.api_key = config('STRIPE_SECRET')

        subscription_data = request.get_json()

        payment_intent_id = subscription_data['payment_intent_id']
        customer_id = subscription_data['customer_id']
        plan = subscription_data['plan']

        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        if payment_intent.status != 'succeeded':
            return jsonify({'message': 'Payment not completed'}), 400

        payment_method_id = payment_intent.payment_method

        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{'price': plan}],
            default_payment_method=payment_method_id
        )

        if not subscription:
            return jsonify({'message': 'Subscription creation failed'}), 202

        return jsonify({'message': 'Subscription created successfully', 'subscription_id': subscription.id}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 400





    
@api.route('/cancel_subscription', methods=['POST'])
def cancel_subscription():
    try:
        if not g.user.subscription_id:
            return jsonify({'message': 'User not found or no active subscription'}), 404

        stripe.api_key = config('STRIPE_SECRET')

        subscription = stripe.Subscription.retrieve(g.user.subscription_id)

        # Check if the subscription is already cancelled
        if subscription.status == 'canceled' or subscription['cancel_at_period_end']:
            end_date = datetime.fromtimestamp(subscription.current_period_end).strftime('%Y-%m-%d')
            return jsonify({'message': f'Subscription is already cancelled and will end on {end_date}'}), 200

        stripe.Subscription.modify(
            g.user.subscription_id,
            cancel_at_period_end=True,
        )

        end_date = datetime.fromtimestamp(subscription.current_period_end).strftime('%Y-%m-%d')

        lg.add_logs(g.client_ip, g.user.id, 3000, f'Subscription canceled End date: {end_date} Sub_id: {g.user.subscription_id}')

        return jsonify({'message': f'Subscription was successfuly cancelled and will end on {end_date}'}), 200

    except Exception as e:
        logging.info(e)
        return jsonify({'message': f'{e}'}), 401


    
