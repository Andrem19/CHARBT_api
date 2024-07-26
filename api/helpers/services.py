import string
import random
import boto3
import os

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'gif', 'png'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def select_random_file(map_dict):
    if len(map_dict) == 1:
        return next(iter(map_dict.values()))
    else:
        sorted_files = sorted(map_dict.values())
        length = len(sorted_files)
        index_end = int(length * 0.85)
        index_start = int(length * 0.15)
        return random.choice(sorted_files[index_start:index_end])


def random_string(length=10):
    """Generate a random string of fixed length."""
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for _ in range(length))

def find_file_containing_previous_timestamp(current_timestamp, map_dict):
    timestamps = sorted(map(int, map_dict.keys()))
    filenames = [map_dict[str(timestamp)] for timestamp in timestamps]

    def binary_search(left, right):
        if left > right:
            if right >= 0:
                return filenames[right]
            else:
                return None

        mid = (left + right) // 2
        start_timestamp = timestamps[mid]
        end_timestamp = int(filenames[mid].split('_')[1].split('.')[0])

        if start_timestamp <= current_timestamp <= end_timestamp:
            return filenames[mid]
        elif current_timestamp < start_timestamp:
            return binary_search(left, mid - 1)
        else:
            return binary_search(mid + 1, right)

    return binary_search(0, len(timestamps) - 1)




def find_file_containing_timestamp(current_timestamp, map_dict):
    timestamps = sorted(map(int, map_dict.keys()))
    filenames = [map_dict[str(timestamp)] for timestamp in timestamps]

    def binary_search(left, right):
        if left > right:
            return None

        mid = (left + right) // 2
        start_timestamp = timestamps[mid]
        end_timestamp = int(filenames[mid].split('_')[1].split('.')[0])
        
        if current_timestamp == end_timestamp:
            if mid + 1 < len(filenames):
                return filenames[mid + 1], False
            else:
                return None, None
        elif start_timestamp <= current_timestamp < end_timestamp:
            return filenames[mid], True
        elif current_timestamp < start_timestamp:
            return binary_search(left, mid - 1)
        else:
            return binary_search(mid + 1, right)

    return binary_search(0, len(timestamps) - 1)

def get_timeframe(timeframe):
    timeframe_dict = {60: '1h', 1440: '1d'}
    return timeframe_dict.get(timeframe, f'{timeframe}m')

def download_dir(prefix, local, bucket, client):
    """
    params:
    - prefix: pattern to match in s3
    - local: local path to folder in which to place files
    - bucket: s3 bucket with target contents
    - client: initialized s3 client object
    """
    keys = []
    dirs = []
    next_token = ''
    base_kwargs = {
        'Bucket':bucket,
        'Prefix':prefix,
    }
    while next_token is not None:
        kwargs = base_kwargs.copy()
        if next_token != '':
            kwargs.update({'ContinuationToken': next_token})
        results = client.list_objects_v2(**kwargs)
        contents = results.get('Contents')
        for i in contents:
            k = i.get('Key')
            if k[-1] != '/':
                keys.append(k)
            else:
                dirs.append(k)
        next_token = results.get('NextContinuationToken')
    for d in dirs:
        dest_pathname = os.path.join(local, d)
        if not os.path.exists(os.path.dirname(dest_pathname)):
            os.makedirs(os.path.dirname(dest_pathname))
    for k in keys:
        dest_pathname = os.path.join(local, k)
        if not os.path.exists(os.path.dirname(dest_pathname)):
            os.makedirs(os.path.dirname(dest_pathname))
        client.download_file(bucket, k, dest_pathname)

