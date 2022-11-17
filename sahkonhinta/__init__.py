import os

from flask import Flask
from . import db, webapp

def create_app(test_config=None):
    # create and config app

    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.root_path, 'db/sahkonhinta.db'),
        UPLOAD_FOLDER=os.path.join(app.root_path, 'uploads'),
        MAX_CONTENT_LENGTH=2 * 1000 * 1000  # max upload size 2 MB
    )

    # if test_config is None:
    #     app.config.from_pyfile('config.py', silent=True)
    # else:
    #     app.config.from_mapping(test_config)

    try:
        os.makedirs(app.root_path)
    except OSError:
        pass
    
    app.register_blueprint(webapp.bp)
    
    return app
    
    
