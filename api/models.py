from flask_login import UserMixin
from __init__ import db
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone, timedelta
import random
import json
import helpers.email_service as emserv
import uuid
import helpers.services as serv
from enum import Enum
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID

class RoleEnum(Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"

class Admin(UserMixin, db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    username = db.Column(db.String(64), index=True, unique=False)
    sessionCode = db.Column(db.String(80), default='')
    role = db.Column(SQLEnum(RoleEnum))
    password_hash = db.Column(db.String(500))
    allowed_ip = db.relationship('AllowedIp', backref='user', lazy='dynamic')

class AllowedIp(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('admin.id'))
    ip = db.Column(db.String(128))

class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(1000), nullable=True)
    video_url = db.Column(db.String(1000), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    comments_on = db.Column(db.Boolean, default=False)
    user = db.relationship('User')
    poll = db.relationship('Poll', uselist=False, back_populates='blog_post')
    comments = db.relationship('Comment', lazy=True, overlaps="blog_post,comments")
    pinned = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'img_url': self.img_url,
            'video_url': self.video_url,
            'comments_on': self.comments_on,
            'pinned': self.pinned,
            'user_id': self.user_id,
            'timestamp': self.timestamp,
            'poll': self.poll.to_dict() if self.poll else None,
            'comments': [comment.to_dict() for comment in self.comments]
        }

class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(100), nullable=False)
    blog_post_id = db.Column(db.Integer, db.ForeignKey('blog_post.id'), nullable=False)
    blog_post = db.relationship('BlogPost', back_populates='poll')
    options = db.relationship('PollOption', cascade="all, delete-orphan", overlaps="poll,options")
    disabled = db.Column(db.Boolean, default=False)
    to_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc) + timedelta(days=1))
    rewardPaid = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'question': self.question,
            'blog_post_id': self.blog_post_id,
            'options': [option.to_dict() for option in self.options],
            'disabled': self.disabled,
            'to_date': self.to_date,
        }

class PollOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    votes = db.relationship('Vote', cascade="all, delete-orphan", overlaps="poll_option,votes")
    poll = db.relationship('Poll', backref=db.backref('poll_options', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'poll_id': self.poll_id,
            'votes': [vote.to_dict() for vote in self.votes]
        }
    
class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    poll_option_id = db.Column(db.Integer, db.ForeignKey('poll_option.id'), nullable=False)
    user = db.relationship('User')
    poll_option = db.relationship('PollOption', overlaps="votes")

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'poll_option_id': self.poll_option_id,
        }
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blog_post_id = db.Column(db.Integer, db.ForeignKey('blog_post.id'), nullable=False)
    user = db.relationship('User')
    blog_post = db.relationship('BlogPost', overlaps="comments")

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'timestamp': self.timestamp,
            'user_id': self.user_id,
            'blog_post_id': self.blog_post_id,
        }

class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)
    refcode = db.Column(db.String(40), default=lambda: str(uuid.uuid4())[:14].replace('-', ''))
    myrefer = db.Column(db.String(40), default='')
    username = db.Column(db.String(64), index=True, unique=False)
    email = db.Column(db.String(120), unique=True)
    email_confirmed = db.Column(db.Boolean, default=False)
    password_hash = db.Column(db.String(500))
    tokens = db.Column(db.Integer, default=0)
    name_changed = db.Column(db.Integer, default=0)
    avatarLink = db.Column(db.String(200), default='')
    badge = db.Column(db.String(200), default='')
    token = db.Column(db.String(500))

    settings_id = db.Column(db.Integer, db.ForeignKey('settings.id'))
    settings = db.relationship('Settings', backref='user', uselist=False)

    payment_status = db.Column(db.String(64), default='default')
    subscription_to = db.Column(db.Integer, default=0)
    subscription_id = db.Column(db.String(64), default='')

    current_session_id = db.Column(db.Integer)
    sessions = db.relationship('Session', backref='user', lazy='dynamic')
    selfdatas = db.relationship('SelfData', backref='user', lazy='dynamic')

    ip_list = db.Column(db.String(1000))
    last_visit = db.Column(db.Integer, default=lambda: datetime.now().timestamp())
    registration_date = db.Column(db.Integer, default=lambda: datetime.now().timestamp())
    delete_account = db.Column(db.Boolean, default=False)
    change_email = db.Column(db.String(120), default='')
    lastTiket = db.Column(db.String(120), default='')
    blogLastVisit = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    sessionCode = db.Column(db.String(80), default='')
    login_ip = db.Column(db.String(80))

    data_size = db.Column(db.Integer, default=0)

    logs = db.relationship('Logs', backref='user', lazy='dynamic')
    add_info = db.Column(db.String(800), default='')

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rightScale = db.Column(db.Boolean, default=False)
    timeScale = db.Column(db.Boolean, default=False)
    showMarkers = db.Column(db.Boolean, default=True)
    showTpsl = db.Column(db.Boolean, default=True)
    showPatterns = db.Column(db.Boolean, default=True)
    showTools = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class SelfData(db.Model):
    __tablename__ = 'selfdata'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), default='')
    cursor = db.Column(db.Integer, default=100)
    path = db.Column(db.String(800))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    size = db.Column(db.Integer, default=0)

    
class GlobalSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(128), default='v1')
    blogLastPost = db.Column(db.DateTime, default=datetime.utcnow())
    blogOn = db.Column(db.Boolean, default=False)
    startTheme = db.Column(db.String(40))
    position_in_session = db.Column(db.Integer, default=2000)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_name = db.Column(db.String(128))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    balance = db.Column(db.Float)
    current_PnL = db.Column(db.Float)
    coin_pair = db.Column(db.String(32))
    timeframe = db.Column(db.Integer)
    additional_timaframe = db.Column(db.Integer)
    positions = db.relationship('Position', backref='session', lazy='dynamic')
    cursor = db.Column(db.Integer, default=100)
    is_self_data = db.Column(db.Boolean, default=False)
    add_info = db.Column(db.String(800), default='')

class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    user_id = db.Column(db.Integer)
    coin_pair = db.Column(db.String(32))
    take_profit = db.Column(db.Float, default=0)
    stop_loss = db.Column(db.Float, default=0)
    open_price = db.Column(db.Float)
    close_price = db.Column(db.Float)
    profit = db.Column(db.Float)
    open_time = db.Column(db.BigInteger)
    close_time = db.Column(db.BigInteger)
    timeframe = db.Column(db.Integer)
    volatility = db.Column(db.Float, default=0)
    amount = db.Column(db.Float)
    target_len = db.Column(db.Integer)
    type_of_close = db.Column(db.String(32))
    buy_sell = db.Column(db.String(32), default='Buy')
    data_ident = db.Column(db.String(80))
    add_info = db.Column(db.String(800), default='')

class Logs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action_code = db.Column(db.Integer)
    description = db.Column(db.String(128))
    timestamp = db.Column(db.Integer)
    ip_address = db.Column(db.String(80))
    add_info = db.Column(db.String(800), default='')

class BlackList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(128))
    to = db.Column(db.DateTime)
    reason = db.Column(db.String(500))

class PaymentPlans(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    token_price_day = db.Column(db.Integer)
    price_subscription_month_1 = db.Column(db.Float)
    price_subscription_year_1 = db.Column(db.Float)
    price_subscription_month_2 = db.Column(db.Float)
    price_subscription_year_2 = db.Column(db.Float)
    price_id_month = db.Column(db.String(120))
    price_id_annualy = db.Column(db.String(120))
    access = db.relationship('PlanAccess', backref='paymentplans', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'token_price_day': self.token_price_day,
            'price_subscription_month_1': self.price_subscription_month_1,
            'price_subscription_year_1': self.price_subscription_year_1,
            'price_subscription_month_2': self.price_subscription_month_2,
            'price_subscription_year_2': self.price_subscription_year_2,
            'access': [access.to_dict() for access in self.access]
        }

class PlanAccess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paymentplans_id = db.Column(db.Integer, db.ForeignKey(PaymentPlans.id))
    name = db.Column(db.String(200))
    description = db.Column(db.String(500))
    number = db.Column(db.Integer, default=1)
    all = db.Column(db.Integer, default=1)
    on = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'paymentplans_id': self.paymentplans_id,
            'name': self.name,
            'number': self.number,
            'all': self.all,
            'description': self.description,
            'on': self.on
        }

class TextDb(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name_id = db.Column(db.String(200))
    name = db.Column(db.String(200))
    text = db.Column(db.String(20000))
    date = db.Column(db.Date, default=datetime.now)

def data_seed():

    globalSettings = GlobalSettings(version='v1', blogLastPost=datetime.now(), startTheme='light', blogOn=True)
    db.session.add(globalSettings)
    db.session.commit()
    pp = '''1. Introduction

    Welcome to Charbt (“we,” “us,” or “our”). We value your privacy and are committed to protecting your personal data. This Privacy Policy explains how we collect, use, safeguard, and disclose your personal information when you use our website and services.

    2. Information We Collect

    We collect and process the following personal data about you:

    Account Information: When you create an account, we collect your email address, password, and name. The email address is used for account creation, login, and communication purposes.
    Payment Information: If you make a payment, we collect your payment information, such as your credit card number and billing address. All payment transactions are processed by Stripe, a third-party payment processor. We do not store or process your payment information on our servers. For more information on Stripe’s privacy practices, please visit their Privacy Policy.
    Usage Data: We collect information about how you use our website and services, such as your IP address, browser type, and pages you visit.
    3. How We Use Your Information

    We use the collected information for the following purposes:

    Account Management: To create and manage your account.
    Communication: To send you updates, notifications, and other information related to your account.
    Service Improvement: To analyze and enhance the performance and usability of our service.
    Payment Processing: To process your payments.
    Fraud Prevention: To prevent fraud and abuse.
    4. Sharing Your Information

    We do not share your personal information with third parties except in the following limited circumstances:

    With your consent: We may share your information with third parties if you consent to such sharing.
    To comply with the law: We may share your information if we are required to do so by law or by a court order.
    To protect our rights: We may share your information if we believe it is necessary to protect our rights or property.
    5. Data Security

    We implement industry-standard security measures to protect your personal data from unauthorized access, use, or disclosure. Our website uses SSL encryption to ensure secure communication between your browser and our server. However, no method of transmission over the Internet or method of electronic storage is 100% secure. Therefore, we cannot guarantee the absolute security of your personal information.

    6. User Rights

    You have the right to:

    Access Your Data: You can request a copy of the personal data we hold about you.
    Rectify Your Data: You can correct any inaccuracies in your personal data.
    Delete Your Data: You can delete your account and all associated personal data from our system.
    To exercise these rights, please visit your account settings or contact us at support@charbt.com.

    7. Data Retention

    We retain your personal data for as long as necessary to provide you with our services and to comply with our legal obligations. Once your data is no longer needed, we will securely delete or anonymize it.

    8. Third-Party Services

    We may employ third-party companies and individuals to facilitate our services. These third parties have access to your personal data only to perform specific tasks on our behalf and are obligated not to disclose or use it for any other purpose.

    9. Changes to This Privacy Policy

    We may update our Privacy Policy from time to time. If we make any material changes, we will notify you by email or by posting a notice on our website. You are advised to review this Privacy Policy periodically for any changes.

    10. Contact Us

    If you have any questions about this Privacy Policy, please contact us at:

    Charbt Support
    Email: support@charbt.com'''

    tos = '''**1. Introduction**

    Welcome to Charbt. This website provides a platform for users to practice and enhance their trading skills.

    **2. Eligibility**

    You must be at least 18 years old to use Charbt.

    **3. Account Registration**

    To use Charbt, you must create an account. You agree to provide accurate and complete information when creating your account. You are responsible for maintaining the confidentiality of your account password and for all activities that occur under your account.

    **4. User Conduct**

    You agree not to use Charbt for any illegal or unauthorized purpose. You also agree not to use Charbt in any way that could damage, disable, overburden, or impair Charbt or interfere with the use of Charbt by any other party.

    **5. Data Processing and Commercial Use**

    CBT has every right to process all data about the user’s trading actions on the CBT resource and extract any useful information from them, as well as its further commercial use.

    **6. Intellectual Property**

    Charbt owns or licenses all intellectual property rights in Charbt, including its trademarks, copyrights, and trade secrets. You may not use any of Charbt's intellectual property without our prior written consent.

    **7. Termination**

    We may terminate your account at any time, with or without notice. You may also terminate your account at any time by contacting us at support@charbt.com.

    **8. Disclaimer of Warranties**

    CHARBT IS PROVIDED "AS IS" AND WITHOUT ANY WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. WE DO NOT WARRANT THAT CHARBT WILL BE UNINTERRUPTED OR ERROR-FREE.

    **9. Limitation of Liability**

    IN NO EVENT SHALL WE BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR EXEMPLARY DAMAGES, INCLUDING BUT NOT LIMITED TO, DAMAGES FOR LOSS OF PROFITS, GOODWILL, USE, DATA, OR OTHER INTANGIBLE LOSSES (EVEN IF WE HAVE BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES) ARISING FROM OR IN CONNECTION WITH THE USE OF CHARBT.

    **10. Indemnification**

    You agree to indemnify, defend, and hold us harmless from and against any and all claims, damages, losses, costs, expenses, and fees (including reasonable attorneys' fees) arising out of or in connection with your use of Charbt.

    **11. Governing Law**

    These Terms shall be governed by and construed in accordance with the laws of the United Kingdom.

    **12. Entire Agreement**

    These Terms constitute the entire agreement between you and us with respect to the subject matter hereof and supersede all prior or contemporaneous communications, representations, or agreements, whether oral or written.

    **13. Severability**

    If any provision of these Terms is held to be invalid or unenforceable, such provision shall be struck from these Terms and the remaining provisions shall remain in full force and effect.

    **14. Waiver**

    No waiver of any provision of these Terms shall be effective unless in writing and signed by both you and us.

    **15. Translation**

    These Terms may be translated into multiple languages in the future. In the event of any inconsistency or discrepancy between the English version and a translated version, the English version shall prevail.

    **16. No Refunds**
    
    All payments made to Charbt are non-refundable. Once a payment is made, it cannot be refunded for any reason. However, you may cancel your subscription at any time to stop any future charges according to your plan.

    **17. Service Interruptions

    We reserve the right to disable the website or certain features of the website for maintenance periods. During these times, the website or certain features may be unavailable.
    
    **18. Single Device Access**

    Access to Charbt is allowed from only one device at a time. If you log in from another device, the session on the previous device will become invalid.
    
    '''

    privacy_policy = TextDb(name='Privacy Policy', name_id='privacy_policy', text=pp, date=datetime.now().date())
    terms_of_service = TextDb(name='Terms Of Service', name_id='terms_of_service', text=tos, date=datetime.now().date())

    db.session.add(privacy_policy)
    db.session.add(terms_of_service)

    plan1 = PaymentPlans(
        name='Essential', 
        token_price_day=10, 
        price_id_month='price_1PluVOJlOCgKlIIv01eCXfoa', 
        price_id_annualy='price_1PlofAJlOCgKlIIvCZ0yWJHu', 
        price_subscription_month_1=35.99, 
        price_subscription_year_1=431.88, 
        price_subscription_month_2=28.99, 
        price_subscription_year_2=347.88
    )

    plan2 = PaymentPlans(
        name='Premium', 
        token_price_day=15, 
        price_id_month='price_1PmgyQJlOCgKlIIvVMGWZaep', 
        price_id_annualy='price_1PloYaJlOCgKlIIvimo1yNnb', 
        price_subscription_month_1=47.99, 
        price_subscription_year_1=575.88, 
        price_subscription_month_2=38.99, 
        price_subscription_year_2=467.88
    )

    plan3 = PaymentPlans(
        name='Premium-Plus', 
        token_price_day=20, 
        price_id_month='price_1PloXjJlOCgKlIIvGj99pzLg', 
        price_id_annualy='price_1PloXGJlOCgKlIIvxkCq00BY', 
        price_subscription_month_1=59.99, 
        price_subscription_year_1=719.88, 
        price_subscription_month_2=47.99, 
        price_subscription_year_2=575.88
    )

    db.session.add(plan1)
    db.session.add(plan2)
    db.session.add(plan3)
    db.session.commit()
    #============1 plan=================
    access11 = PlanAccess(paymentplans_id=plan1.id, name='5 Trading Pairs', number=5, all=21, description='Access to 5 trading pairs: BTCUSDT, ETHUSDT, BNBUSDT, AAPL, EURUSD', on=True)
    access12 = PlanAccess(paymentplans_id=plan1.id, name='Save 100 Charts', number=100, all=1000, description='Ability to save up to 100 charts', on=True)
    access121 = PlanAccess(paymentplans_id=plan1.id, name='10 Sessions', number=10, all=100, description='You can have up to 10 sessions at the same time, to create new ones you will need to delete old ones', on=True)
    access122 = PlanAccess(paymentplans_id=plan1.id, name='Auxiliary Timeframe', number=1, all=100, description='You can have 1 auxiliary timeframe, which will follow the main one as you trade.', on=False)
    access123 = PlanAccess(paymentplans_id=plan1.id, name='Detailed statistics', number=1, all=100, description='Detailed statistics with visualizations, graphs and detailed data.', on=False)
    access124 = PlanAccess(paymentplans_id=plan1.id, name='Saving session data in csv', number=1, all=100, description='You can save session data for each position with candles and situation as well as position type and result in csv format to use this data for research purposes or training machine learning models.', on=False)
    access125 = PlanAccess(paymentplans_id=plan1.id, name='Voting in polls', description='You can vote in polls regarding the introduction of new features for the service on our blog.(blog under development)', on=True)
    access13 = PlanAccess(paymentplans_id=plan1.id, name='1 Day Timeframe', description='Access to 1 day timeframe', on=True)
    access14 = PlanAccess(paymentplans_id=plan1.id, name='1 Hour Timeframe', description='Access to 1 hour timeframe', on=True)
    access15 = PlanAccess(paymentplans_id=plan1.id, name='30 Minute Timeframe', description='Access to 30 minute timeframe', on=False)
    access16 = PlanAccess(paymentplans_id=plan1.id, name='5 Minute Timeframe', description='Access to 5 minute timeframe', on=False)
    access17 = PlanAccess(paymentplans_id=plan1.id, name='1 Minute Timeframe', description='Access to 1 minute timeframe', on=False)
    access18 = PlanAccess(paymentplans_id=plan1.id, name='Personal dataset', description='', on=False)

    db.session.add(access11)
    db.session.add(access12)
    db.session.add(access121)
    db.session.add(access13)
    db.session.add(access14)
    db.session.add(access15)
    db.session.add(access16)
    db.session.add(access17)
    db.session.add(access122)
    db.session.add(access123)
    db.session.add(access124)
    db.session.add(access125)
    db.session.add(access18)

    db.session.commit()
    #============2 plan=================
    access21 = PlanAccess(paymentplans_id=plan2.id, name='All Trading Pairs', number=21, all=21, description='Access to all trading pairs on the platform', on=True)
    access22 = PlanAccess(paymentplans_id=plan2.id, name='Save 500 Charts', number=500, all=1000, description='Ability to save up to 500 charts', on=True)
    access221 = PlanAccess(paymentplans_id=plan2.id, name='50 Sessions', number=50, all=100, description='You can have up to 50 sessions at the same time, to create new ones you will need to delete old ones', on=True)
    access222 = PlanAccess(paymentplans_id=plan2.id, number=1, all=100, name='Auxiliary Timeframe', description='You can have 1 auxiliary timeframe, which will follow the main one as you trade.', on=False)
    access223 = PlanAccess(paymentplans_id=plan2.id, name='Detailed statistics', number=1, all=100, description='Detailed statistics with visualizations, graphs and detailed data.', on=True)
    access224 = PlanAccess(paymentplans_id=plan2.id, name='Saving session data in csv', number=1, all=100, description='You can save session data for each position with candles and situation as well as position type and result in csv format to use this data for research purposes or training machine learning models.', on=False)
    access225 = PlanAccess(paymentplans_id=plan2.id, name='Voting in polls', description='You can vote in polls regarding the introduction of new features for the service on our blog.(blog under development)', on=True)
    access23 = PlanAccess(paymentplans_id=plan2.id, name='1 Day Timeframe', description='Access to 1 day timeframe', on=True)
    access24 = PlanAccess(paymentplans_id=plan2.id, name='1 Hour Timeframe', description='Access to 1 hour timeframe', on=True)
    access25 = PlanAccess(paymentplans_id=plan2.id, name='30 Minute Timeframe', description='Access to 30 minute timeframe', on=True)
    access26 = PlanAccess(paymentplans_id=plan2.id, name='5 Minute Timeframe', description='Access to 5 minute timeframe', on=False)
    access27 = PlanAccess(paymentplans_id=plan2.id, name='1 Minute Timeframe', description='Access to 1 minute timeframe', on=False)
    access28 = PlanAccess(paymentplans_id=plan1.id, name='Personal dataset', description='You can upload 200MB your data set for testing and simulation of the trading process', on=True)

    db.session.add(access21)
    db.session.add(access22)
    db.session.add(access221)
    db.session.add(access23)
    db.session.add(access24)
    db.session.add(access25)
    db.session.add(access26)
    db.session.add(access27)
    db.session.add(access222)
    db.session.add(access223)
    db.session.add(access224)
    db.session.add(access225)
    db.session.add(access28)

    db.session.commit()
    #============3 plan=================
    access31 = PlanAccess(paymentplans_id=plan3.id, name='All Trading Pairs', number=21, all=21, description='Access to all trading pairs on the platform', on=True)
    access32 = PlanAccess(paymentplans_id=plan3.id, name='Save 1000 Charts', number=1000, all=1000, description='Ability to save up to 1000 charts', on=True)
    access321 = PlanAccess(paymentplans_id=plan3.id, name='100 Sessions', number=100, all=100, description='You can have up to 100 sessions at the same time, to create new ones you will need to delete old ones', on=True)
    access322 = PlanAccess(paymentplans_id=plan3.id, name='Auxiliary Timeframe', number=100, all=100, description='You can have 1 auxiliary timeframe, which will follow the main one as you trade.', on=True)
    access323 = PlanAccess(paymentplans_id=plan3.id, name='Detailed statistics', number=1, all=100, description='Detailed statistics with visualizations, graphs and detailed data.', on=True)
    access324 = PlanAccess(paymentplans_id=plan3.id, name='Saving session data in csv', number=1, all=100, description='You can save session data for each position with candles and situation as well as position type and result in csv format to use this data for research purposes or training machine learning models.', on=True)
    access325 = PlanAccess(paymentplans_id=plan3.id, name='Voting in polls', description='You can vote in polls regarding the introduction of new features for the service on our blog.(blog under development)', on=True)
    access33 = PlanAccess(paymentplans_id=plan3.id, name='1 Day Timeframe', description='Access to 1 day timeframe', on=True)
    access34 = PlanAccess(paymentplans_id=plan3.id, name='1 Hour Timeframe', description='Access to 1 hour timeframe', on=True)
    access35 = PlanAccess(paymentplans_id=plan3.id, name='30 Minute Timeframe', description='Access to 30 minute timeframe', on=True)
    access36 = PlanAccess(paymentplans_id=plan3.id, name='5 Minute Timeframe', description='Access to 5 minute timeframe', on=True)
    access37 = PlanAccess(paymentplans_id=plan3.id, name='1 Minute Timeframe', description='Access to 1 minute timeframe', on=True)
    access38 = PlanAccess(paymentplans_id=plan1.id, name='Personal dataset', description='You can upload 1GB your data set for testing and simulation of the trading process', on=True)

    db.session.add(access31)
    db.session.add(access32)
    db.session.add(access321)
    db.session.add(access33)
    db.session.add(access34)
    db.session.add(access35)
    db.session.add(access36)
    db.session.add(access37)
    db.session.add(access322)
    db.session.add(access323)
    db.session.add(access324)
    db.session.add(access325)
    db.session.add(access38)

    db.session.commit()

    # Clear the database (destructive operation)
    # db.reflect()
    # db.drop_all()
    # db.create_all()

    # Create test users with different roles and payment statuses
    password='Oad106zfyvjo'#str(uuid.uuid4())
    admin = Admin(username='curuvar', password_hash=generate_password_hash(password), role=RoleEnum.ADMIN.name)
    db.session.add(admin)
    db.session.commit()
    # emserv.send_servce_info_msg('7255591@gmail.com', 'service@charbt.com', f'psw: {password}')
    alIp1 = AllowedIp(ip='86.4.138.8', user_id=admin.id)
    alIp2 = AllowedIp(ip='172.19.0.1', user_id=admin.id)
    alIp3 = AllowedIp(ip='192.168.128.1', user_id=admin.id)
    db.session.add(alIp1)
    db.session.add(alIp2)
    db.session.add(alIp3)
    db.session.commit()

    ips = ['134.555.321.233']
    ip_list = json.dumps(ips)
    users = [
        User(email="user@example.com", email_confirmed=True, ip_list=ip_list, username="user", password_hash=generate_password_hash("userpassword"), payment_status='premium-plus', settings=Settings(), badge='green'),
        User(email="user2@example.com", tokens=200, email_confirmed=True, ip_list=ip_list, username="user2", password_hash=generate_password_hash("userpassword2"), payment_status='default', settings=Settings()),
        User(email="user3@example.com", email_confirmed=True, ip_list=ip_list, username="user3", password_hash=generate_password_hash("userpassword3"), payment_status='premium-plus', settings=Settings(), badge='green'),
        User(email="moderator@example.com", email_confirmed=True, ip_list=ip_list, username="moderator", password_hash=generate_password_hash("moderatorpassword"), payment_status='premium', settings=Settings()),
        User(email="admin@example.com", email_confirmed=True, ip_list=ip_list, username="admin", password_hash=generate_password_hash("adminpassword"), payment_status='essential', settings=Settings()),
        User(email="7255591@gmail.com", email_confirmed=True, ip_list=ip_list, username="Andrem", password_hash=generate_password_hash("Oad106zfyvjo"), payment_status='default', settings=Settings()),
    ]

    # Add users to the session
    for user in users:
        db.session.add(user)

    # Create test sessions for each user
    sessions = [
        Session(user_id=i+1, coin_pair='BTCUSDT', timeframe=60, additional_timaframe=1440, session_name=serv.random_string().upper(), balance=random.uniform(1000, 5000), current_PnL=random.uniform(-100, 100)) for i in range(len(users))
    ]

    # Add sessions to the session
    for session in sessions:
        db.session.add(session)
    db.session.commit()

    post1 = BlogPost(title='', content='At the end of the voting period, prize tokens will be distributed to everyone who chose the correct answer.', user_id=1, img_url='https://charbtmarketdata.s3.amazonaws.com/BLOG_IMG/Screenshot_2024-07-24_141215.png')
    db.session.add(post1)
    db.session.commit()

    # Создаем голосование для первого поста
    poll1 = Poll(question='Up or Down?', blog_post_id=post1.id, disabled=False, to_date=datetime.now(timezone.utc) + timedelta(days=1))
    db.session.add(poll1)
    db.session.commit()

    # Создаем варианты ответа для голосования
    option1 = PollOption(name='Up', poll_id=poll1.id)
    option2 = PollOption(name='Down', poll_id=poll1.id)
    db.session.add(option1)
    db.session.add(option2)

    db.session.commit()

    vote1 = Vote(user_id=1, poll_option_id=option1.id)
    vote2 = Vote(user_id=2, poll_option_id=option2.id)
    vote3 = Vote(user_id=3, poll_option_id=option1.id)
    db.session.add(vote1)
    db.session.add(vote2)
    db.session.add(vote3)

    db.session.commit()

    # Update current_session_id for each user
    for i, user in enumerate(users):
        user.current_session_id = sessions[i].id

    # Create test positions for each session
    # try:
    #     positions = [
    #         Position(session_id=i+1, coin_pair="BTCUSDT", open_price=round(random.uniform(30000, 60000), 2), close_price=round(random.uniform(30000, 60000), 2), profit=random.uniform(-100, 100), open_time=int(datetime.now().timestamp()*1000), close_time=int(datetime.now().timestamp()*1000) + 300000, amount=random.uniform(0.01, 1), target_len=random.randint(10, 100), type_of_close="stop_loss", buy_sell=random.choice(["Buy", "Sell"])) for i in range(len(sessions))
    #     ]
    # except Exception as e:
    #     print(e)
    # # Add positions to the session
    # for position in positions:
    #     db.session.add(position)

    db.session.commit()

    print("Test users, sessions, and positions added successfully!")
