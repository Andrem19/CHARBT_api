from models import SelfData
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
            data = [row for row in csv_reader]
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
        if original_size_mb > 5:
            return jsonify({'message': 'The data file should not be larger than 5MB'}), 404
        
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

        size_mb_exist = serv.check_folder(g.user.id, name)
        total_size = size_mb_exist + original_size_mb
        if (g.user.payment_status.lower() == 'premium-plus' and total_size>=1000) or (g.user.payment_status.lower() == 'premium' and total_size>=200):
            return jsonify({'message': 'You have reached your limit or want to exceed it. increase your limit or upgrade to a plan with a higher data limit.'}), 404

        g.user.data_size = total_size
        path=f'{g.user.id}/{name}'
        self_data = SelfData(cursor=100, path=path, user_id=g.user.id, size=original_size_mb)
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