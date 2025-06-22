class DatabaseRouter:
    """
    Database router to separate user and session data into different databases
    """
    
    user_models = {'FarmerUser', 'SchemeEligibility'}
    session_models = {'ChatSession', 'SessionMessage'}
    
    def db_for_read(self, model, **hints):
        """Suggest the database to read from."""
        if model._meta.object_name in self.user_models:
            return 'default'  # sanchalak_users
        elif model._meta.object_name in self.session_models:
            return 'sessions'  # sanchalak_sessions
        return None
    
    def db_for_write(self, model, **hints):
        """Suggest the database to write to."""
        if model._meta.object_name in self.user_models:
            return 'default'  # sanchalak_users
        elif model._meta.object_name in self.session_models:
            return 'sessions'  # sanchalak_sessions
        return None
    
    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations if models are in the same database."""
        db_set = {'default', 'sessions'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure that certain apps' models get created on the right database."""
        if app_label == 'telegram_app':
            if model_name in ['farmeruser', 'schemeeligibility']:
                return db == 'default'
            elif model_name in ['chatsession', 'sessionmessage']:
                return db == 'sessions'
        return None 