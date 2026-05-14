from models import BlogPost, PollOption, Vote
from datetime import datetime, timezone
from flask import jsonify, request, jsonify, g, make_response
from __init__ import db, api

@api.route('/blog_posts', methods=['GET'])
def get_blog_posts():
    user_id = g.user.id
    try:
        g.user.blogLastVisit = datetime.now(timezone.utc)
        db.session.commit()
        posts = BlogPost.query.all()
        blog_data = []
        for post in posts:
            post_dict = post.to_dict()
            post_dict['isVoted'] = False
            if post_dict['poll']:

                for option in post_dict['poll']['options']:
                    if post_dict['isVoted'] == False:
                        if any(vote['user_id'] == user_id for vote in option['votes']):
                            post_dict['isVoted'] = True
                    option['votes'] = len(option['votes'])
            blog_data.append(post_dict)
        return jsonify(blog_data), 200
    except Exception as e:
        print(jsonify({'Message': e}))
        return make_response(jsonify({'Message': e}), 500)


@api.route('/vote', methods=['POST'])
def vote():
    try:
        data = request.get_json()
        post_id = data.get('postId')
        option_id = data.get('optionId')

        post = BlogPost.query.get(post_id)
        option = PollOption.query.get(option_id)

        if not post or not option or option.poll.blog_post_id != post.id:
            return jsonify({'message': 'Invalid postId or optionId'}), 400

        if option.poll is None or option.poll.disabled or (option.poll.to_date is not None and option.poll.to_date.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)):
            return jsonify({'message': 'Poll is disabled or expired'}), 400


        existing_vote = Vote.query.filter_by(user_id=g.user.id, poll_option_id=option.id).first()
        if existing_vote:
            return jsonify({'message': 'User has already voted'}), 400

        new_vote = Vote(user_id=g.user.id, poll_option_id=option.id)
        db.session.add(new_vote)
        db.session.commit()

        user_id = g.user.id
        posts = BlogPost.query.all()
        blog_data = []
        for post in posts:

            post_dict = post.to_dict()
            post_dict['isVoted'] = False
            if post_dict['poll']:

                for option in post_dict['poll']['options']:
                    if post_dict['isVoted'] == False:
                        if any(vote['user_id'] == user_id for vote in option['votes']):
                            post_dict['isVoted'] = True
                    option['votes'] = len(option['votes'])
            blog_data.append(post_dict)
        return jsonify(blog_data), 200
    except Exception as e:
        print(jsonify({'Message': e}))
        return make_response(jsonify({'Message': e}), 500)