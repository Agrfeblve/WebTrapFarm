import json
import os

import requests

try:
    from config_loader import load_app_config
except ImportError:
    from src.config_loader import load_app_config


def _filer_url():
    return load_app_config()["seaweedfs"]["filer_url"].rstrip("/")


def _mongodb_client():
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise RuntimeError(
            "MongoDB support requires the optional 'pymongo' package"
        ) from exc
    return MongoClient(load_app_config()["database"]["mongodb_uri"])


def upload_to_filer(local_path, remote_path):
    """
    Upload a local file to a specified Filer path.

    :param local_path: Local file path.
    :param remote_path: Destination path in SeaweedFS, such as /dataset3/image.png.
    """
    url = f"{_filer_url()}{remote_path}"

    with open(local_path, "rb") as local_file:
        response = requests.post(url, files={"file": local_file})

    if response.status_code in (200, 201):
        print(f"Upload succeeded: {response.json()}")
    else:
        print(f"Upload failed: {response.status_code}, {response.text}")


def upload_folder_recursively(local_dir, remote_dir):
    """Upload every file below a local directory while preserving its structure."""
    remote_dir = "/" + remote_dir.strip("/")
    filer_base_url = _filer_url()
    session = requests.Session()
    success_count = 0
    fail_count = 0

    for root, _dirs, files in os.walk(local_dir):
        for file_name in files:
            local_file_path = os.path.join(root, file_name)
            relative_path = os.path.relpath(local_file_path, local_dir)
            # SeaweedFS paths always use forward slashes, including on Windows.
            remote_file_path = os.path.join(remote_dir, relative_path).replace("\\", "/")
            url = f"{filer_base_url}{remote_file_path}"

            try:
                # Binary mode avoids accidental text encoding conversions.
                with open(local_file_path, "rb") as local_file:
                    response = session.post(url, files={"file": local_file})

                if response.status_code in (200, 201):
                    success_count += 1
                else:
                    print(f"Upload failed [{response.status_code}]: {remote_file_path}")
                    fail_count += 1
            except Exception as exc:
                print(f"Error while processing {file_name}: {exc}")
                fail_count += 1

    print("\n--- Upload task finished ---")
    print(f"Succeeded: {success_count} files")
    print(f"Failed: {fail_count} files")
    print(f"Destination: {remote_dir}")


def delete_seaweed_directory(directory_path):
    """
    Delete a directory from SeaweedFS recursively.

    :param directory_path: Remote directory path, such as /dataset3/temp_logs.
    """
    url = f"{_filer_url()}{directory_path}?recursive=true"

    try:
        response = requests.delete(url)
        if response.status_code == 204:
            print(f"Directory deleted: {directory_path}")
        elif response.status_code == 404:
            print("Directory does not exist")
        else:
            print(f"Delete failed, status {response.status_code}: {response.text}")
    except Exception as exc:
        print(f"Request failed: {exc}")


def upload_json_to_mongodb(json_file_path, db_name, collection_name):
    """Insert a JSON object or list into a MongoDB collection."""
    client = _mongodb_client()
    database = client[db_name]
    collection = database[collection_name]

    try:
        with open(json_file_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)

        if isinstance(data, list):
            result = collection.insert_many(data)
            print(f"Inserted {len(result.inserted_ids)} records")
        else:
            result = collection.insert_one(data)
            print(f"Inserted one record with ID: {result.inserted_id}")
    except Exception as exc:
        print(f"MongoDB upload failed: {exc}")
    finally:
        client.close()


def update_key_to_mongodb(key_name, value_obj, task_id, step, db_name, collection_name):
    """Upsert one key for a task step in a MongoDB collection."""
    client = _mongodb_client()
    database = client[db_name]
    collection = database[collection_name]
    query = {"task_id": task_id, "step": step}
    collection.update_one(query, {"$set": {key_name: value_obj}}, upsert=True)
    client.close()
