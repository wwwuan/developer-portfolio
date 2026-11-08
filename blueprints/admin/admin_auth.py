from flask import Blueprint,jsonify,request
from exts import db
import logging
from models import AdminUserModel
from werkzeug.security import generate_password_hash,check_password_hash
from forms import AdminRegisterForm,LoginForm
from flask_jwt_extended import  create_access_token
import jwt
from config import JWT_SECRET_KEY,SECURITY_KEY

logger = logging.getLogger(__name__)

bp=Blueprint('admin_auth',__name__,url_prefix='/admin_auth')


@bp.route("/register",methods=['POST'])
def register():
    #用户注册API接收表单格式
    # 检查请求内容类型
    if not request.form:
        return jsonify({
            'status': 'error',
            'message': 'Content-Type必须为application/form'
        }), 400

    #验证验证码是否正确
    try:
        form=AdminRegisterForm(request.form)
        if form.validate():
            #创建用户
            email=form.email.data
            username=form.username.data
            password=form.password.data
            admin=AdminUserModel(email=email,username=username,password=generate_password_hash(password))
            db.session.add(admin)
            db.session.commit()
            return jsonify({
                "status":'success',
                "message":"管理员账户注册成功"
            }),200
        else:
            print(form.errors)
            return jsonify({
                'status': 'error',
                'message': form.errors
            }), 401
    except Exception as e:
        print(e)
        return jsonify({
            "states": 'error',
            "message":str(e)
        })

@bp.route('/login',methods=['POST'])
def login():
    if not request.is_json:
        return jsonify({
            'status': 'error',
            'message': 'Content-Type必须为application/json'
        }), 400
    form=LoginForm(data=request.get_json())
    if form.validate():
        email=form.email.data
        password=form.password.data
        admin=AdminUserModel.query.filter_by(email=email,status='active').first()

        if admin:
            if check_password_hash(admin.password, password):
                #生成token
                access_token = create_access_token(
                    identity=str(admin.id),
                    additional_claims={"admin_id":admin.id,"password_version":admin.password_version,"security_token":SECURITY_KEY}
                )
                payload = jwt.decode(access_token, JWT_SECRET_KEY, algorithms=["HS256"])
                print(payload)
                return jsonify({
                    'status': 'success',
                    'message': '登录成功',
                    'admin_id': admin.id,
                    'username': admin.username,
                    'access_token': access_token
                }), 200
            else:
                #若验证失败
                return jsonify({
                    'status': 'error',
                    'message': '用户名或密码错误'
                }), 401

        else:
            print(form.errors)
            return jsonify({
                'status': 'error',
                'message':"数据获取失败"
            })
    else:
        print(form.errors)
        return jsonify({
            'status': 'error',
            'message': form.errors
        }), 401
