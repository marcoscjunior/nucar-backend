import os
import json
import uuid
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId

# --- Configuration ---
app = Flask(__name__)
CORS(app)

# --- MongoDB Connection ---
# The connection string is stored securely as an environment variable in Render.
MONGO_URI = os.environ.get('MONGO_URI')
if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable not set.")

client = MongoClient(MONGO_URI)
db = client.nucar_db # The database name

# --- UPLOAD FOLDER (Still needed for PDF reports) ---
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# --- Helper to convert MongoDB ObjectId to string ---
def mongo_to_json(data):
    if isinstance(data, list):
        return [mongo_to_json(item) for item in data]
    if isinstance(data, dict):
        if '_id' in data:
            data['id'] = str(data['_id'])
            del data['_id']
        return {key: mongo_to_json(value) for key, value in data.items()}
    return data

# --- Frontend Route ---
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

# --- API Routes ---

# Login and User (CPF) Management
@app.route('/api/login', methods=['POST'])
def login():
    cpf_to_check = request.json.get('cpf')
    user = db.users.find_one({"cpf": cpf_to_check})
    if user:
        return jsonify({"success": True, "message": "Login successful"}), 200
    # Check for the default user if the collection is empty
    if db.users.count_documents({}) == 0 and cpf_to_check == "74892016357":
        db.users.insert_one({"cpf": "74892016357"})
        return jsonify({"success": True, "message": "Default user login"}), 200
    return jsonify({"success": False, "message": "CPF not authorized"}), 401

@app.route('/api/users', methods=['GET'])
def get_users():
    users_cursor = db.users.find({}, {"_id": 0, "cpf": 1})
    users_list = [user['cpf'] for user in users_cursor]
    return jsonify(users_list)

@app.route('/api/users', methods=['POST'])
def add_user():
    cpf_to_add = request.json.get('cpf')
    if cpf_to_add and not db.users.find_one({"cpf": cpf_to_add}):
        db.users.insert_one({"cpf": cpf_to_add})
        return jsonify({"success": True, "cpf": cpf_to_add}), 201
    return jsonify({"error": "Invalid or duplicate CPF"}), 400

@app.route('/api/users/<cpf>', methods=['DELETE'])
def delete_user(cpf):
    result = db.users.delete_one({"cpf": cpf})
    if result.deleted_count > 0:
        return jsonify({"success": True}), 200
    return jsonify({"error": "CPF not found"}), 404

# Waiting List Management
@app.route('/api/waitinglist', methods=['GET'])
def get_waiting_list():
    items = list(db.waiting_list.find())
    return jsonify(mongo_to_json(items))

@app.route('/api/waitinglist', methods=['POST'])
def add_waiting_list_item():
    item = request.json
    result = db.waiting_list.insert_one(item)
    item['id'] = str(result.inserted_id)
    return jsonify(mongo_to_json(item)), 201

@app.route('/api/waitinglist/<item_id>', methods=['PUT'])
def update_waiting_list_item(item_id):
    update_data = request.json
    result = db.waiting_list.update_one(
        {'_id': ObjectId(item_id)},
        {'$set': {'name': update_data.get('name'), 'count': update_data.get('count')}}
    )
    if result.matched_count > 0:
        updated_item = db.waiting_list.find_one({'_id': ObjectId(item_id)})
        return jsonify(mongo_to_json(updated_item)), 200
    return jsonify({"error": "Item not found"}), 404

@app.route('/api/waitinglist/<item_id>', methods=['DELETE'])
def delete_waiting_list_item(item_id):
    result = db.waiting_list.delete_one({'_id': ObjectId(item_id)})
    if result.deleted_count > 0:
        return jsonify({"success": True}), 200
    return jsonify({"error": "Item not found"}), 404

# Provider (Contract) Routes
@app.route('/api/providers', methods=['GET'])
def get_providers():
    providers = list(db.providers.find())
    return jsonify(mongo_to_json(providers))

@app.route('/api/providers', methods=['POST'])
def add_provider():
    new_provider = request.json
    new_provider['execution'] = {}
    result = db.providers.insert_one(new_provider)
    new_provider['id'] = str(result.inserted_id)
    return jsonify(mongo_to_json(new_provider)), 201

@app.route('/api/providers/<provider_id>', methods=['PUT'])
def update_provider(provider_id):
    updated_data = request.json
    # Ensure we don't overwrite execution data
    existing_provider = db.providers.find_one({'_id': ObjectId(provider_id)})
    if not existing_provider:
        return jsonify({"error": "Provider not found"}), 404
    updated_data['execution'] = existing_provider.get('execution', {})
    
    db.providers.update_one({'_id': ObjectId(provider_id)}, {'$set': updated_data})
    return jsonify({"success": True}), 200

@app.route('/api/providers/<provider_id>', methods=['DELETE'])
def delete_provider(provider_id):
    result = db.providers.delete_one({'_id': ObjectId(provider_id)})
    if result.deleted_count > 0:
        return jsonify({"success": True}), 200
    return jsonify({"error": "Provider not found"}), 404

# Execution Data Routes
@app.route('/api/providers/<provider_id>/execution', methods=['PUT'])
def update_execution(provider_id):
    execution_update = request.json
    month_key = execution_update['monthKey']
    execution_data = execution_update['data']
    
    result = db.providers.update_one(
        {'_id': ObjectId(provider_id)},
        {'$set': {f'execution.{month_key}': execution_data}}
    )
    if result.matched_count > 0:
        return jsonify({"success": True}), 200
    return jsonify({"error": "Provider not found"}), 404

@app.route('/api/providers/<provider_id>/execution/<month_key>', methods=['DELETE'])
def delete_execution(provider_id, month_key):
    result = db.providers.update_one(
        {'_id': ObjectId(provider_id)},
        {'$unset': {f'execution.{month_key}': ""}}
    )
    if result.matched_count > 0:
        return jsonify({"success": True}), 200
    return jsonify({"error": "Execution data not found"}), 404

# Report Routes
@app.route('/api/reports', methods=['GET'])
def get_reports():
    reports = list(db.reports.find())
    return jsonify(mongo_to_json(reports))

@app.route('/api/reports', methods=['POST'])
def add_report():
    if 'report_pdf' not in request.files: return jsonify({"error": "No file part"}), 400
    file = request.files['report_pdf']
    if file.filename == '': return jsonify({"error": "No selected file"}), 400
    if file:
        filename = f"{generate_id('report')}_{file.filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        new_report = { "name": request.form['name'], "description": request.form['description'], "filename": filename }
        db.reports.insert_one(new_report)
        return jsonify(mongo_to_json(new_report)), 201
    return jsonify({"error": "File upload failed"}), 500

@app.route('/api/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/reports/<report_id>', methods=['DELETE'])
def delete_report(report_id):
    report_to_delete = db.reports.find_one({'_id': ObjectId(report_id)})
    if report_to_delete:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], report_to_delete['filename']))
        except OSError as e:
            print(f"Error deleting file: {e}")
        db.reports.delete_one({'_id': ObjectId(report_id)})
        return jsonify({"success": True}), 200
    return jsonify({"error": "Report not found"}), 404

# Reguladores, Etiquetas, Bloqueio Routes (converted to MongoDB)
@app.route('/api/reguladores', methods=['GET', 'POST'])
def handle_reguladores():
    if request.method == 'GET':
        return jsonify(mongo_to_json(list(db.reguladores.find())))
    if request.method == 'POST':
        new_regulador = request.json
        db.reguladores.insert_one(new_regulador)
        return jsonify(mongo_to_json(new_regulador)), 201

@app.route('/api/reguladores/<regulador_id>', methods=['PUT', 'DELETE'])
def handle_single_regulador(regulador_id):
    if request.method == 'PUT':
        db.reguladores.update_one({'_id': ObjectId(regulador_id)}, {'$set': request.json})
        return jsonify({"success": True})
    if request.method == 'DELETE':
        db.reguladores.delete_one({'_id': ObjectId(regulador_id)})
        return jsonify({"success": True})

@app.route('/api/etiquetas', methods=['GET', 'POST'])
def handle_etiquetas():
    if request.method == 'GET':
        etiquetas = db.etiquetas.find_one() or {}
        return jsonify(mongo_to_json(etiquetas))
    if request.method == 'POST':
        update = request.json
        tipo = update['type']
        db.etiquetas.update_one(
            {},
            {
                '$push': {f'{tipo}.history': update['entry']},
                '$set': {f'{tipo}.current_start': update['next_start']}
            },
            upsert=True
        )
        return jsonify({"success": True})

@app.route('/api/bloqueio/providers', methods=['GET', 'POST'])
def handle_bloqueio_providers():
    if request.method == 'GET':
        return jsonify(mongo_to_json(list(db.bloqueio_providers.find())))
    if request.method == 'POST':
        new_provider = request.json
        db.bloqueio_providers.insert_one(new_provider)
        return jsonify(mongo_to_json(new_provider)), 201

@app.route('/api/bloqueio/providers/<provider_id>', methods=['PUT'])
def update_bloqueio_provider(provider_id):
    db.bloqueio_providers.update_one({'_id': ObjectId(provider_id)}, {'$set': request.json})
    return jsonify({"success": True})

@app.route('/api/bloqueio/alteracoes', methods=['GET', 'POST'])
def handle_bloqueio_alteracoes():
    if request.method == 'GET':
        return jsonify(mongo_to_json(list(db.bloqueio_alteracoes.find())))
    if request.method == 'POST':
        new_alteracao = request.json
        db.bloqueio_alteracoes.insert_one(new_alteracao)
        return jsonify(mongo_to_json(new_alteracao)), 201

# --- Main Execution ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
