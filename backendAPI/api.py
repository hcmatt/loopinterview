from application import app, db
from application.databaseModel import StoreInit, StoreStatus, MenuHours


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'StoreInit': StoreInit, 'StoreStatus': StoreStatus, 'MenuHours': MenuHours}