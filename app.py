import os
import json
import uuid
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# --- Configuration ---
app = Flask(__name__)
CORS(app)

# --- IMPORTANT: Path configuration for Render Persistent Disks ---
# Render will mount the disk at the specified path, e.g., /data
DATA_DIR = '/data'
DATABASE_FILE = os.path.join(DATA_DIR, 'database.json')
UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the data directory and upload folder exist on the persistent disk
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Helper Functions ---

def get_db_data():
    """Reads all data from the JSON database file."""
    if not os.path.exists(DATABASE_FILE):
        # If the file doesn't exist, create it with a default structure
        default_data = {
            "providers": [],
            "reports": [],
            "reguladores": [],
            "etiquetas": {
                "aih-mac": {"history": [], "current_start": "282510110834"},
                "aih-faec": {"history": [], "current_start": "282550000201"},
                "apac-mac": {"history": [], "current_start": "282520119134"},
                "apac-faec": {"history": [], "current_start": "282560000251"}
            },
            "bloqueio_providers": [],
            "bloqueio_alteracoes": [],
            "users": ["74892016357"], # Default CPF for initial access
            "waiting_list": [] 
        }
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, indent=4)
        return default_data
    try:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content:
                # If file is empty, return a default structure to avoid errors
                return get_db_data()
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_db_data(data):
    """Saves the entire data object to the JSON database file."""
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def generate_id(prefix):
    """Generates a unique ID with a given prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

# --- API Routes ---

# Login and User (CPF) Management
@app.route('/api/login', methods=['POST'])
def login():
    data = get_db_data()
    users = data.get('users', [])
    cpf_to_check = request.json.get('cpf')
    if cpf_to_check in users:
        return jsonify({"success": True, "message": "Login successful"}), 200
    return jsonify({"success": False, "message": "CPF not authorized"}), 401

@app.route('/api/users', methods=['GET'])
def get_users():
    data = get_db_data()
    return jsonify(data.get('users', []))

@app.route('/api/users', methods=['POST'])
def add_user():
    data = get_db_data()
    users = data.get('users', [])
    cpf_to_add = request.json.get('cpf')
    if cpf_to_add and cpf_to_add not in users:
        users.append(cpf_to_add)
        data['users'] = users
        save_db_data(data)
        return jsonify({"success": True, "cpf": cpf_to_add}), 201
    return jsonify({"error": "Invalid or duplicate CPF"}), 400

@app.route('/api/users/<cpf>', methods=['DELETE'])
def delete_user(cpf):
    data = get_db_data()
    users = data.get('users', [])
    if cpf in users:
        users.remove(cpf)
        data['users'] = users
        save_db_data(data)
        return jsonify({"success": True}), 200
    return jsonify({"error": "CPF not found"}), 404

# Waiting List Management
@app.route('/api/waitinglist', methods=['GET'])
def get_waiting_list():
    data = get_db_data()
    return jsonify(data.get('waiting_list', []))

@app.route('/api/waitinglist', methods=['POST'])
def add_waiting_list_item():
    data = get_db_data()
    waiting_list = data.get('waiting_list', [])
    item = request.json
    item['id'] = generate_id('wait')
    waiting_list.append(item)
    data['waiting_list'] = waiting_list
    save_db_data(data)
    return jsonify(item), 201

@app.route('/api/waitinglist/<item_id>', methods=['PUT'])
def update_waiting_list_item(item_id):
    data = get_db_data()
    waiting_list = data.get('waiting_list', [])
    item_index = next((i for i, item in enumerate(waiting_list) if item['id'] == item_id), None)
    if item_index is not None:
        update_data = request.json
        waiting_list[item_index]['name'] = update_data.get('name', waiting_list[item_index]['name'])
        waiting_list[item_index]['count'] = update_data.get('count', waiting_list[item_index]['count'])
        data['waiting_list'] = waiting_list
        save_db_data(data)
        return jsonify(waiting_list[item_index]), 200
    return jsonify({"error": "Item not found"}), 404

@app.route('/api/waitinglist/<item_id>', methods=['DELETE'])
def delete_waiting_list_item(item_id):
    data = get_db_data()
    waiting_list = data.get('waiting_list', [])
    new_list = [item for item in waiting_list if item['id'] != item_id]
    if len(new_list) < len(waiting_list):
        data['waiting_list'] = new_list
        save_db_data(data)
        return jsonify({"success": True}), 200
    return jsonify({"error": "Item not found"}), 404


# Provider (Contract) Routes
@app.route('/api/providers', methods=['GET'])
def get_providers():
    data = get_db_data()
    return jsonify(data.get('providers', []))

@app.route('/api/providers', methods=['POST'])
def add_provider():
    new_provider = request.json
    new_provider['id'] = generate_id('provider')
    new_provider['execution'] = {}
    data = get_db_data()
    providers = data.get('providers', [])
    providers.append(new_provider)
    data['providers'] = providers
    save_db_data(data)
    return jsonify(new_provider), 201

@app.route('/api/providers/<provider_id>', methods=['PUT'])
def update_provider(provider_id):
    updated_data = request.json
    data = get_db_data()
    providers = data.get('providers', [])
    provider_index = next((i for i, p in enumerate(providers) if p['id'] == provider_id), None)
    if provider_index is not None:
        updated_data['execution'] = providers[provider_index].get('execution', {})
        providers[provider_index] = updated_data
        providers[provider_index]['id'] = provider_id
        data['providers'] = providers
        save_db_data(data)
        return jsonify({"success": True}), 200
    return jsonify({"error": "Provider not found"}), 404

@app.route('/api/providers/<provider_id>', methods=['DELETE'])
def delete_provider(provider_id):
    data = get_db_data()
    providers = data.get('providers', [])
    new_providers = [p for p in providers if p['id'] != provider_id]
    if len(new_providers) < len(providers):
        data['providers'] = new_providers
        save_db_data(data)
        return jsonify({"success": True}), 200
    return jsonify({"error": "Provider not found"}), 404

# Execution Data Routes
@app.route('/api/providers/<provider_id>/execution', methods=['PUT'])
def update_execution(provider_id):
    execution_update = request.json
    month_key = execution_update['monthKey']
    execution_data = execution_update['data']
    data = get_db_data()
    provider = next((p for p in data.get('providers', []) if p['id'] == provider_id), None)
    if provider:
        if 'execution' not in provider: provider['execution'] = {}
        provider['execution'][month_key] = execution_data
        save_db_data(data)
        return jsonify({"success": True}), 200
    return jsonify({"error": "Provider not found"}), 404

@app.route('/api/providers/<provider_id>/execution/<month_key>', methods=['DELETE'])
def delete_execution(provider_id, month_key):
    data = get_db_data()
    provider = next((p for p in data.get('providers', []) if p['id'] == provider_id), None)
    if provider and 'execution' in provider and month_key in provider['execution']:
        del provider['execution'][month_key]
        save_db_data(data)
        return jsonify({"success": True}), 200
    return jsonify({"error": "Execution data not found"}), 404

# Report Routes
@app.route('/api/reports', methods=['GET'])
def get_reports():
    data = get_db_data()
    return jsonify(data.get('reports', []))

@app.route('/api/reports', methods=['POST'])
def add_report():
    if 'report_pdf' not in request.files: return jsonify({"error": "No file part"}), 400
    file = request.files['report_pdf']
    if file.filename == '': return jsonify({"error": "No selected file"}), 400
    if file:
        filename = f"{generate_id('report')}_{file.filename}"
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        new_report = {
            "id": generate_id('report_meta'),
            "name": request.form['name'],
            "description": request.form['description'],
            "filename": filename
        }
        data = get_db_data()
        reports = data.get('reports', [])
        reports.append(new_report)
        data['reports'] = reports
        save_db_data(data)
        return jsonify(new_report), 201
    return jsonify({"error": "File upload failed"}), 500

@app.route('/api/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/reports/<report_id>', methods=['DELETE'])
def delete_report(report_id):
    data = get_db_data()
    reports = data.get('reports', [])
    report_to_delete = next((r for r in reports if r['id'] == report_id), None)
    if report_to_delete:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], report_to_delete['filename']))
        except OSError as e:
            print(f"Error deleting file {report_to_delete['filename']}: {e}")
        new_reports = [r for r in reports if r['id'] != report_id]
        data['reports'] = new_reports
        save_db_data(data)
        return jsonify({"success": True}), 200
    return jsonify({"error": "Report not found"}), 404

# Reguladores Routes
@app.route('/api/reguladores', methods=['GET', 'POST'])
def handle_reguladores():
    data = get_db_data()
    reguladores = data.get('reguladores', [])
    if request.method == 'GET':
        return jsonify(reguladores)
    if request.method == 'POST':
        new_regulador = request.json
        new_regulador['id'] = generate_id('regulador')
        reguladores.append(new_regulador)
        data['reguladores'] = reguladores
        save_db_data(data)
        return jsonify(new_regulador), 201

@app.route('/api/reguladores/<regulador_id>', methods=['PUT', 'DELETE'])
def handle_single_regulador(regulador_id):
    data = get_db_data()
    reguladores = data.get('reguladores', [])
    regulador_index = next((i for i, r in enumerate(reguladores) if r['id'] == regulador_id), None)
    if regulador_index is None:
        return jsonify({"error": "Regulador not found"}), 404
    if request.method == 'PUT':
        reguladores[regulador_index] = request.json
        reguladores[regulador_index]['id'] = regulador_id
        data['reguladores'] = reguladores
        save_db_data(data)
        return jsonify(reguladores[regulador_index])
    if request.method == 'DELETE':
        del reguladores[regulador_index]
        data['reguladores'] = reguladores
        save_db_data(data)
        return jsonify({"success": True})

# Etiquetas Routes
@app.route('/api/etiquetas', methods=['GET', 'POST'])
def handle_etiquetas():
    data = get_db_data()
    etiquetas = data.get('etiquetas', {})
    if request.method == 'GET':
        return jsonify(etiquetas)
    if request.method == 'POST':
        update = request.json
        tipo = update['type']
        if tipo in etiquetas:
            etiquetas[tipo]['history'].append(update['entry'])
            etiquetas[tipo]['current_start'] = update['next_start']
            data['etiquetas'] = etiquetas
            save_db_data(data)
            return jsonify({"success": True})
        return jsonify({"error": "Invalid etiqueta type"}), 400

# Bloqueio Routes
@app.route('/api/bloqueio/providers', methods=['GET', 'POST'])
def handle_bloqueio_providers():
    data = get_db_data()
    providers = data.get('bloqueio_providers', [])
    if request.method == 'GET':
        return jsonify(providers)
    if request.method == 'POST':
        new_provider = request.json
        new_provider['id'] = generate_id('bloqueio_p')
        providers.append(new_provider)
        data['bloqueio_providers'] = providers
        save_db_data(data)
        return jsonify(new_provider), 201

@app.route('/api/bloqueio/providers/<provider_id>', methods=['PUT'])
def update_bloqueio_provider(provider_id):
    data = get_db_data()
    providers = data.get('bloqueio_providers', [])
    provider_index = next((i for i, p in enumerate(providers) if p['id'] == provider_id), None)
    if provider_index is not None:
        providers[provider_index] = request.json
        providers[provider_index]['id'] = provider_id
        data['bloqueio_providers'] = providers
        save_db_data(data)
        return jsonify(providers[provider_index])
    return jsonify({"error": "Provider not found"}), 404

@app.route('/api/bloqueio/alteracoes', methods=['GET', 'POST'])
def handle_bloqueio_alteracoes():
    data = get_db_data()
    alteracoes = data.get('bloqueio_alteracoes', [])
    if request.method == 'GET':
        return jsonify(alteracoes)
    if request.method == 'POST':
        new_alteracao = request.json
        new_alteracao['id'] = generate_id('bloqueio_a')
        alteracoes.append(new_alteracao)
        data['bloqueio_alteracoes'] = alteracoes
        save_db_data(data)
        return jsonify(new_alteracao), 201

# --- Main Execution ---
if __name__ == '__main__':
    # The port is dynamically assigned by Render, so we don't need to specify it.
    # Host '0.0.0.0' is required to be accessible within the Render network.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
