import os
import json
import uuid
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# --- Configuration ---
app = Flask(__name__)
CORS(app)  # Allows requests from the HTML file

# Define the path for our database file and upload folder
DATABASE_FILE = 'database.json'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
            "bloqueio_alteracoes": []
        }
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, indent=4)
        return default_data
    try:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        # If file is empty, corrupted or not found, return default structure
        return {}

def save_db_data(data):
    """Saves the entire data object to the JSON database file."""
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def generate_id(prefix):
    """Generates a unique ID with a given prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

# --- Frontend Route ---

@app.route('/')
def serve_index():
    """Serves the main index.html file."""
    return send_from_directory('.', 'index.html')

@app.route('/favicon.ico')
def favicon():
    """Serves a blank favicon to avoid 404 errors in the log."""
    return '', 204

# --- API Routes ---

# Provider (Contract) Routes
@app.route('/api/providers', methods=['GET'])
def get_providers():
    data = get_db_data()
    return jsonify(data.get('providers', []))

@app.route('/api/providers', methods=['POST'])
def add_provider():
    new_provider = request.json
    new_provider['id'] = generate_id('provider')
    new_provider['execution'] = {} # Initialize execution data
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
        # Preserve execution data when updating
        updated_data['execution'] = providers[provider_index].get('execution', {})
        providers[provider_index] = updated_data
        providers[provider_index]['id'] = provider_id # Ensure ID is not overwritten
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
        if 'execution' not in provider:
            provider['execution'] = {}
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
    if 'report_pdf' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['report_pdf']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
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
        # Delete file from disk
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], report_to_delete['filename']))
        except OSError as e:
            print(f"Error deleting file {report_to_delete['filename']}: {e}")
        # Remove from DB
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
    # Host '0.0.0.0' makes the server accessible on your local network
    app.run(debug=True, host='0.0.0.0', port=5000)
