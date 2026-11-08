from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from models import UserModel
from exts import mail,r,db
from flask_mail import Message
import string
import random
from forms import RegisterForm,LoginForm,ResetPasswordForm
from werkzeug.security import generate_password_hash,check_password_hash
from flask_jwt_extended import  create_access_token
from config import JWT_SECRET_KEY
import jwt

"""
用户注册与登录，验证码发送
"""

bp=Blueprint('auth',__name__,url_prefix='/auth')



@bp.route('/login',methods=['POST'])
def login():
    #用户登录API接收JSON格式的用户名和密码，验证用户身份
    # 检查请求内容类型
    if not request.is_json:
        return jsonify({
            'status': 'error',
            'message': 'Content-Type必须为application/json'
        }), 400

    # 获取请求数据
    form=LoginForm(data=request.get_json())
    if form.validate():
        email = form.email.data
        password = form.password.data
        user = UserModel.query.filter_by(email=email,status="active").first()

        #验证用户名密码
        if user and check_password_hash(user.password, password):
            #生成token
            access_token = create_access_token(
                identity=str(user.id),
                additional_claims={"id":user.id,"password_version":user.password_version}
            )
            payload = jwt.decode(access_token, JWT_SECRET_KEY, algorithms=["HS256"])
            return jsonify({
            'status': 'success',
            'message': '登录成功',
            'user_id': user.id,
            'username': user.username,
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
            'message':form.errors
        })

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
        form=RegisterForm(request.form)
        if form.validate():
            print("验证通过")
            #创建用户
            email=form.email.data
            username=form.username.data
            password=form.password.data
            user=UserModel(email=email,username=username,password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            return jsonify({
                "status":'success',
                "message":"用户注册成功"
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

@bp.route('/captcha/email',methods=['GET'])
def get_email_captcha():
    """
    接收邮件地址发送验证码
    """
    email = request.args.get("email")
    if not email:
        return jsonify({
            "status": 'error',
            "message":'未正确输入邮箱'
        })
    source = string.digits*4
    captcha=random.sample(source,4)
    captcha="".join(captcha)
    print(captcha)
    try:
        message = Message(subject="注册验证码", recipients=[email], body=f"您的验证码是{captcha}")
        mail.send(message)
        r.setex(email,300,captcha)
        print(f"验证码已发送至{email}")
        return jsonify({
            'status': 'success',
            'message':captcha
        }),200
    except SQLAlchemyError as err:
        print(f"出现错误{err}")
        return jsonify({
            'status': 'error',
            'message':"验证码发送失败"
        }),400


@bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    """重置密码页面"""
    if not request.is_json:
        return jsonify({
            'status': 'error',
            'message': 'Content-Type必须为application/json'
        }), 400

    # 获取请求数据
    form=ResetPasswordForm(data=request.get_json())

    if form.validate():
        print("验证通过，处理密码重置逻辑")
        email = form.email.data
        new_password = form.new_password.data

        try:
            # 查找用户
            user = UserModel.query.filter_by(email=email, status="active").first()
            if user:
                # 更新密码（假设用户模型有 set_password 方法）
                user.password=generate_password_hash(new_password)
                db.session.commit()

                return jsonify({
                    'status': 'success',
                    'message': '密码重置成功，请使用新密码登录'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': "该邮箱未被注册"
                })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': '密码重置失败'
            })
    print("基础验证未通过",form.errors)
    return jsonify({
        'status': 'error',
        'message': form.errors
    })
