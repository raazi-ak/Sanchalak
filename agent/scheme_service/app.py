# app.py

from flask import Flask, request, jsonify
from scheme_service import SchemeService, SchemeRepository
from eligibility_checker import EligibilityChecker

app = Flask(__name__)
repo = SchemeRepository()
service = SchemeService(repo)
checker = EligibilityChecker()

@app.route('/api/schemes', methods=['GET', 'POST'])
def schemes():
    if request.method == 'GET':
        return jsonify(service.list())
    elif request.method == 'POST':
        data = request.get_json()
        scheme, errors = service.create(data)
        if errors:
            return jsonify({"errors": errors}), 400
        return jsonify(scheme), 201

@app.route('/api/schemes/<scheme_id>', methods=['GET', 'PUT', 'DELETE'])
def scheme_detail(scheme_id):
    if request.method == 'GET':
        scheme = service.get(scheme_id)
        if not scheme:
            return jsonify({"error": "Not found"}), 404
        return jsonify(scheme)
    elif request.method == 'PUT':
        data = request.get_json()
        scheme, errors = service.update(scheme_id, data)
        if not scheme:
            return jsonify({"error": "Not found"}), 404
        if errors:
            return jsonify({"errors": errors}), 400
        return jsonify(scheme)
    elif request.method == 'DELETE':
        success = service.delete(scheme_id)
        if not success:
            return jsonify({"error": "Not found"}), 404
        return '', 204

@app.route('/api/eligibility/check/<scheme_id>', methods=['POST'])
def check_eligibility(scheme_id):
    applicant = request.get_json()
    scheme = service.get(scheme_id)
    if not scheme:
        return jsonify({"error": "Scheme not found"}), 404
    result = checker.check(applicant, scheme)
    return jsonify(result.to_dict())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
