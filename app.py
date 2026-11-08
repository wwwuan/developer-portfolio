from flask import Flask,jsonify
import config
from exts import db,mail,r,Jwt
from blueprints.auth import bp as auth_bp
from blueprints.file_processing.photo_transfer import bp as pt_bp
from blueprints.file_processing.result_download import bp as rd_bp
from blueprints.file_processing.files_preview import bp as fp_bp
from blueprints.user_home import bp as uh_bp
from blueprints.admin.admin_auth import bp as aa_bp
from blueprints.file_processing.project_select import bp as ap_bp
from blueprints.admin.admin_user import bp as au_bp
from blueprints.admin.admin_error import bp as ae_bp
from flask_migrate import Migrate
from scheduler import init_scheduler
import logging
import os


def create_app():
    app = Flask(__name__)
    app.config.from_object(config)

    db.init_app(app)
    migrate = Migrate(app, db)
    mail.init_app(app)
    r.init_app(app)
    Jwt.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(pt_bp)
    app.register_blueprint(uh_bp)
    app.register_blueprint(rd_bp)
    app.register_blueprint(fp_bp)
    app.register_blueprint(aa_bp)
    app.register_blueprint(ap_bp)
    app.register_blueprint(au_bp)
    app.register_blueprint(ae_bp)

    return app


os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(module)s:%(lineno)d] %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

app = create_app()

init_scheduler(app)

@app.route('/',methods=['GET','POST'])
def hello_world():  # put application's code here
    return jsonify('Hello World!')

if __name__ == '__main__':
    app.run()
