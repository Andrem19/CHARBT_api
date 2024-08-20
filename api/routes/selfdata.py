from models import SelfData, Session, Position
import logging
import csv
from flask import jsonify, request, jsonify, g
from __init__ import db, s3, api, cache
import helpers.services as serv
import io

@api.route('/download_data/<int:selfdata_id>', methods=['GET'])
def download_data(selfdata_id):
    try:
        @cache.memoize(timeout=120)
        def cached_data_return(selfdata_id):
            bucket = 'charbtmarketdata'
            folder_prefix = 'SELF_DATA/'

            self_data = SelfData.query.get(selfdata_id)
            if not self_data:
                return jsonify({'message': 'Data not found'}), 404
            if self_data.user_id != g.user.id:
                return jsonify({'message': 'Data not belong to user'}), 404
            
            full_path = f"{folder_prefix}{self_data.path}"
            
            response = s3.get_object(Bucket=bucket, Key=full_path)
            csv_content = response['Body'].read().decode('utf-8')
            

            csv_reader = csv.reader(io.StringIO(csv_content))

            data = []
            for row in csv_reader:
                converted_row = [int(row[0])] + [float(value) for value in row[1:]]
                data.append(converted_row)
                
            return jsonify({'data': data}), 200
        
        return cached_data_return(selfdata_id)
        
    except Exception as e:
        logging.error(e, exc_info=True)
        return jsonify({'message': 'Internal server error'}), 500

@api.route('/delete_data/<int:selfdata_id>', methods=['DELETE'])
def delete_data(selfdata_id):
    try:
        bucket = 'charbtmarketdata'
        folder_prefix = 'SELF_DATA/'

        self_data = SelfData.query.get(selfdata_id)
        if not self_data:
            return jsonify({'message': 'Data not found'}), 404
        
        if self_data.user_id != g.user.id:
            return jsonify({'message': 'Data not belong to user'}), 404
        
        g.user.data_size-=self_data.size

        full_path = f"{folder_prefix}{self_data.path}"
        
        s3.delete_object(Bucket=bucket, Key=full_path)

        sessions = Session.query.filter_by(selfdataid=selfdata_id).all()
        for session in sessions:
            Position.query.filter_by(session_id=session.id).delete()
            db.session.delete(session)
        
        previous_session = Session.query.filter(Session.user_id == g.user.id).order_by(Session.id.desc()).first()
        g.user.current_session_id = previous_session.id
        
        db.session.delete(self_data)

        db.session.commit()
        
        return jsonify({'message': 'Data successfully deleted'}), 200
    except Exception as e:
        logging.error(e, exc_info=True)
        return jsonify({'message': 'Internal server error'}), 500

@api.route('/upload_data', methods=['POST'])
def upload_data():
    try:
        if not g.user or g.user.payment_status.lower() not in ['premium-plus', 'premium']:
            return jsonify({'message': 'Allowd only for Premium and Premium Plus'}), 404
        
        file = request.files['file']
        
        name = request.form.get('name')
        timestamp_col = int(request.form.get('timestamp'))
        open_col = int(request.form.get('open'))
        high_col = int(request.form.get('high'))
        low_col = int(request.form.get('low'))
        close_col = int(request.form.get('close'))
        volume_col = int(request.form.get('volume'))

        original_size = len(file.read())
        original_size_mb = original_size / (1024 * 1024)
        if original_size_mb > 2.5:
            return jsonify({'message': 'The data file should not be larger than 2.5MB'}), 404
        
        file.seek(0)
        
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.reader(stream)
        
        data = [row for row in csv_input]
        
        if data and not data[0][0].replace('.', '', 1).isdigit():
            data.pop(0)
        
        processed_data = []
        for row in data:
            processed_row = [
                row[timestamp_col-1],
                row[open_col-1],
                row[high_col-1],
                row[low_col-1],
                row[close_col-1],
                row[volume_col-1]
            ]
            processed_data.append(processed_row)
        
        if serv.check_file_exists(g.user.id, name):
            return jsonify({'message': 'Name is already exist in your set'}), 404
        if '.csv' not in name:
            return jsonify({'message': 'The file extension must be .csv'}), 404

        size_mb_exist = serv.check_folder(g.user.id, name)
        total_size = size_mb_exist + original_size_mb
        if (g.user.payment_status.lower() == 'premium-plus' and total_size>=1000) or (g.user.payment_status.lower() == 'premium' and total_size>=200):
            return jsonify({'message': 'You have reached your limit or want to exceed it. increase your limit or upgrade to a plan with a higher data limit.'}), 404

        g.user.data_size = total_size
        path=f'{g.user.id}/{name}'
        self_data = SelfData(name=name, path=path, user_id=g.user.id, size=original_size_mb)
        db.session.add(self_data)
        db.session.commit()

        result = serv.save_to_s3(processed_data, path)
        if result:
            return jsonify({'message': 'Data uploaded successfully'}), 200
        else:
            return jsonify({'message': 'Something went wrong while loading'}), 404

    except Exception as e:
        logging.error(e, exc_info=True)
        return jsonify({'message': 'Internal server error'}), 500
    
@api.route('/save_cursor', methods=['POST'])
def save_cursor():
    try:
        session_id = int(request.json.get('session_id'))
        cursor = int(request.json.get('cursor'))

        session = Session.query.get(session_id)
        if not session or session.user_id != g.user.id:
            return jsonify({'message': 'Session not found or not owned by the current user'}), 404
        
        if not session.is_self_data:
            return jsonify({'message': 'The session must be based on personal data to save the cursor history'}), 404
        
        session.cursor = cursor
        db.session.commit()
        return jsonify({'message': 'Cursor saved successfully'}), 200
    except Exception as e:
        logging.error(e, exc_info=True)
        return jsonify({'message': 'Internal server error'}), 500
    

@api.route('/position_self_data', methods=['GET'])
def position_self_data():
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
            bucket = 'charbtmarketdata'
            folder_prefix = 'SELF_DATA/'
            timestamp_open = int(g.position.open_time) * 1000

            coin_pair = g.position.coin_pair

            dataset_info = SelfData.query.filter_by(name=coin_pair).first()

            if not dataset_info:
                return jsonify({'message': 'Dataset was deleted or never exist'}), 404
            
            if dataset_info.user_id != g.user.id:
                return jsonify({'message': 'Data not belong to user'}), 404
            
            full_path = f"{folder_prefix}{dataset_info.path}"
            
            response = s3.get_object(Bucket=bucket, Key=full_path)
            csv_content = response['Body'].read().decode('utf-8')
            

            csv_reader = csv.reader(io.StringIO(csv_content))
            data = [row for row in csv_reader]
            data = sorted(data, key=lambda x: int(x[0]))

            index_open = next((i for i, row in enumerate(data) if int(row[0]) == timestamp_open), None)
            if index_open is None:
                return jsonify({'message': 'Timestamp open not found in data'}), 404

            start_index = max(0, index_open - 100)

            sliced_data = data[start_index:index_open + 1]

            return jsonify({'data': sliced_data}), 200
        
        return cached_function_position(g.position.id)

    except Exception as e:
        return jsonify({'message': str(e)}), 500