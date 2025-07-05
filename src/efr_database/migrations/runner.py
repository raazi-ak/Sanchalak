import importlib
import os

def get_migration_scripts():
    folder = os.path.dirname(__file__)
    scripts = [f for f in os.listdir(folder) if f.startswith("00") and f.endswith(".py") and f != "__init__.py"]
    scripts.sort()
    return scripts

def run_migrations(db, migration_collection):
    scripts = get_migration_scripts()
    for script in scripts:
        if migration_collection.find_one({"name": script}):
            continue  # Already run
        mod = importlib.import_module(f"src.efr_database.migrations.{script[:-3]}")
        modified = mod.run(db)
        migration_collection.insert_one({"name": script, "modified": modified})
        print(f"✅ Migration {script} applied ({modified} docs updated)") 