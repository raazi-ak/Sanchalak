# scheme_service.py

import os
import json
import uuid
from datetime import datetime
from jsonschema import validate, ValidationError

class SchemeRepository:
    def __init__(self, storage_dir='data/schemes'):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def save(self, scheme: Dict) -> str:
        scheme_id = scheme.get("metadata", {}).get("scheme_id") or str(uuid.uuid4())
        scheme["metadata"]["scheme_id"] = scheme_id
        scheme["metadata"]["modified_date"] = datetime.now().isoformat()
        path = os.path.join(self.storage_dir, f"{scheme_id}.json")
        with open(path, 'w') as f:
            json.dump(scheme, f, indent=2)
        return scheme_id

    def get(self, scheme_id):
        path = os.path.join(self.storage_dir, f"{scheme_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            return json.load(f)

    def delete(self, scheme_id):
        path = os.path.join(self.storage_dir, f"{scheme_id}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def list(self):
        schemes = []
        for fname in os.listdir(self.storage_dir):
            if fname.endswith('.json'):
                with open(os.path.join(self.storage_dir, fname), 'r') as f:
                    schemes.append(json.load(f))
        return schemes

class SchemeService:
    def __init__(self, repo, schema_path='schemas/government_scheme_schema.json'):
        self.repo = repo
        with open(schema_path, 'r') as f:
            self.schema = json.load(f)

    def create(self, scheme):
        errors = self._validate(scheme)
        if errors:
            return None, errors
        scheme_id = self.repo.save(scheme)
        return self.repo.get(scheme_id), []

    def get(self, scheme_id):
        return self.repo.get(scheme_id)

    def update(self, scheme_id, scheme):
        if not self.repo.get(scheme_id):
            return None, ["Scheme not found"]
        errors = self._validate(scheme)
        if errors:
            return scheme, errors
        scheme["metadata"]["scheme_id"] = scheme_id
        self.repo.save(scheme)
        return self.repo.get(scheme_id), []

    def delete(self, scheme_id):
        return self.repo.delete(scheme_id)

    def list(self):
        return self.repo.list()

    def _validate(self, scheme):
        try:
            validate(instance=scheme, schema=self.schema)
            return []
        except ValidationError as e:
            return [e.message]
