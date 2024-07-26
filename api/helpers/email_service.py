from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
import smtplib
import logging

def send_email(email_recipient, email_sender, email_subject, confirmation_link):
    email_password = 'Oad106zfyvjo'

    if email_subject == 'Email Confirmation':
        template_name = 'mail/confirm_email.html'
    elif email_subject == 'Password Recovery':
        template_name = 'mail/password_recovery.html'
    elif email_subject == 'Payment Confirmation':
        template_name = 'mail/payment_confirmation.html'

    file_loader = FileSystemLoader('templates')
    env = Environment(loader=file_loader)
    template = env.get_template(template_name)

    email_message = template.render(confirmation_link=confirmation_link)

    msg = MIMEMultipart()
    msg['From'] = email_sender
    msg['To'] = email_recipient
    msg['Subject'] = email_subject
    msg.attach(MIMEText(email_message, 'html'))  # Используйте 'html' вместо 'plain'

    try:
        server = smtplib.SMTP_SSL('smtp.mail.eu-west-1.awsapps.com', 465)
        server.ehlo()
        server.login(email_sender, email_password)
        text = msg.as_string()
        res = server.sendmail(email_sender, email_recipient, text)
        logging.info(res)
        print('Email sent to %s' % email_recipient)
        server.quit()
    except Exception as e:
        logging.info(e)
        logging.info("SMTP server connection error")
    return True


def send_email_sub_confirm(email_recipient, email_sender, email_subject, name, plan, sub_id):
    email_password = 'Oad106zfyvjo'

    if email_subject == 'Payment Confirmation':
        template_name = 'mail/payment_confirmation.html'
    elif email_subject == 'Subscription Cancelled':
        template_name = 'mail/subscription_canceled.html'

    file_loader = FileSystemLoader('templates')
    env = Environment(loader=file_loader)
    template = env.get_template(template_name)

    email_message = template.render(user_name=name, plan_name=plan, subscription_id=sub_id)

    msg = MIMEMultipart()
    msg['From'] = email_sender
    msg['To'] = email_recipient
    msg['Subject'] = email_subject
    msg.attach(MIMEText(email_message, 'html'))  # Используйте 'html' вместо 'plain'

    try:
        server = smtplib.SMTP_SSL('smtp.mail.eu-west-1.awsapps.com', 465)
        server.ehlo()
        server.login(email_sender, email_password)
        text = msg.as_string()
        res = server.sendmail(email_sender, email_recipient, text)
        logging.info(res)
        print('Email sent to %s' % email_recipient)
        server.quit()
    except Exception as e:
        logging.info(e)
        logging.info("SMTP server connection error")
    return True

def send_tiket(email_recipient, email_sender, email_subject, message, userId, userEmail):
    email_password = 'Oad106zfyvjo'

    template_name = 'mail/tiket.html'

    file_loader = FileSystemLoader('templates')
    env = Environment(loader=file_loader)
    template = env.get_template(template_name)

    email_message = template.render(subject=email_subject, message=message, userId=str(userId), userEmail=userEmail)
    
    msg = MIMEMultipart()
    msg['From'] = email_sender
    msg['To'] = email_recipient
    msg['Subject'] = str(email_subject)
    msg.attach(MIMEText(email_message, 'html'))  # Используйте 'html' вместо 'plain'

    try:
        server = smtplib.SMTP_SSL('smtp.mail.eu-west-1.awsapps.com', 465)
        server.ehlo()
        server.login(email_sender, email_password)
        text = msg.as_string()
        res = server.sendmail(email_sender, email_recipient, text)
        logging.info(res)
        print('Email sent to %s' % email_recipient)
        server.quit()
    except Exception as e:
        print(e)
        logging.info(e)
        logging.info("SMTP server connection error")
    return True

def tiket_created(email_recipient, email_sender, ticketNumber):
    email_password = 'Oad106zfyvjo'


    template_name = 'mail/tiket_created.html'

    file_loader = FileSystemLoader('templates')
    env = Environment(loader=file_loader)
    template = env.get_template(template_name)

    email_message = template.render(ticketNumber=ticketNumber)

    msg = MIMEMultipart()
    msg['From'] = email_sender
    msg['To'] = email_recipient
    msg['Subject'] = f'Tiket #{ticketNumber} created'
    msg.attach(MIMEText(email_message, 'html'))  # Используйте 'html' вместо 'plain'

    try:
        server = smtplib.SMTP_SSL('smtp.mail.eu-west-1.awsapps.com', 465)
        server.ehlo()
        server.login(email_sender, email_password)
        text = msg.as_string()
        res = server.sendmail(email_sender, email_recipient, text)
        logging.info(res)
        print('Email sent to %s' % email_recipient)
        server.quit()
    except Exception as e:
        logging.info(e)
        logging.info("SMTP server connection error")
    return True

def send_servce_info_msg(email_recipient, email_sender, message):
    email_password = 'Oad106zfyvjo'

    email_message = message

    msg = MIMEMultipart()
    msg['From'] = email_sender
    msg['To'] = email_recipient
    msg['Subject'] = 'Message'
    msg.attach(MIMEText(email_message, 'plain'))  # Используйте 'plain' для обычного текста

    try:
        server = smtplib.SMTP_SSL('smtp.mail.eu-west-1.awsapps.com', 465)
        server.ehlo()
        server.login(email_sender, email_password)
        text = msg.as_string()
        res = server.sendmail(email_sender, email_recipient, text)
        print('Email sent to %s' % email_recipient)
        server.quit()
    except Exception as e:
        print("SMTP server connection error")
        print(e)
    return True
