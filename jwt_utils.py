from flask_jwt_extended import  get_jwt, verify_jwt_in_request
from flask import jsonify, g
from functools import wraps
from models import UserModel,AdminUserModel
from config import SECURITY_KEY

def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # 首先验证JWT有效性
            verify_jwt_in_request()

            # 获取JWT claims
            claims = get_jwt()
            user_id = claims.get('sub')  # flask_jwt_extended默认使用'sub'存储用户ID
            password_version = claims.get('password_version', 0)

            # 验证用户和版本号
            user = UserModel.query.filter_by(id=user_id, status="active").first()
            if not user:
                return jsonify({"error": "用户不存在或已被禁用"}), 401

            if password_version != user.password_version:
                return jsonify({"error": "Token版本过期，请重新登录"}), 401
            print("验证成功")

            # 使用g对象存储用户信息（Flask标准做法）
            g.current_user = user
            g.user_id = user_id
            return f(*args, **kwargs)

        except Exception as e:
            print(f"JWT验证错误: {str(e)}")
            return jsonify({
                'status': 'token_error',
                "message": "Token验证失败"
            }), 401

    return decorated_function



def jwt_required_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # 首先验证JWT有效性
            verify_jwt_in_request()

            # 获取JWT claims
            claims = get_jwt()
            admin_id = claims.get('sub')  # flask_jwt_extended默认使用'sub'存储用户ID
            password_version = claims.get('password_version', 0)
            security_token=claims.get('security_token')

            # 验证用户和版本号
            admin = AdminUserModel.query.filter_by(id=admin_id, status="active").first()
            if not admin:
                return jsonify({"error": "管理员账户不存在或已被禁用"}), 401

            if password_version != admin.password_version:
                return jsonify({"error": "Token版本过期，请重新登录"}), 401

            if security_token != SECURITY_KEY:
                return jsonify({"error": "权限验证未通过"}), 401

            # 使用g对象存储用户信息（Flask标准做法）
            g.current_user = admin
            g.user_id = int(admin_id)

            return f(*args, **kwargs)

        except Exception as e:
            print(f"JWT验证错误: {str(e)}")
            return jsonify({"error": "Token验证失败"}), 401

    return decorated_function