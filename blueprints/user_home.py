from exts import db
from jwt_utils import jwt_required
from flask import Blueprint,jsonify,request,g
from models import UserModel,ProjectModel
from forms import ChangePasswordForm
from werkzeug.security import generate_password_hash,check_password_hash
import time
import logging

bp=Blueprint('user_home',__name__,url_prefix='/user_home')

logger = logging.getLogger(__name__)

@bp.route('/',methods=['GET','POST'])
def hello_world():  # put application's code here
    time.sleep(5)
    return jsonify('Hello World!')

@bp.route('/user_select/',endpoint='user_select')
@jwt_required
def user_select():
    try:
        user=g.current_user
        username=user.username
        return jsonify({
            'username':username,
            'email':user.email,
            'status':'success'
        })
    except Exception as e:
        return jsonify({
            'status':'error',
            'message':str(e)
        })

@bp.route('/user_delete',endpoint='user_delete')
@jwt_required
def user_delete():
    try:
        user= g.current_user
        user.soft_delete(user.id)
        return jsonify({
            'status': "success",
            'message':"用户注销成功"
        })
    except Exception as e:
        return jsonify({
            'status': "error",
            'message': f"用户注销失败{str(e)}"
        })

@bp.route('/project_delete',methods=['POST'],endpoint='project_delete')
@jwt_required
def project_delete():
    try:
        user_id = g.user_id
        data = request.get_json()
        project_id=data['project_id']
        project = ProjectModel.query.filter_by(project_id=project_id,is_deleted=False).first()
        if not project:
            return jsonify({
                'status': "error",
                'message':"文件不存在"
            })
        userid=project.user_id

        if userid != user_id:
            return jsonify({
                "states": 'error',
                "message": '无权限删除'
            })

        project.soft_delete(deleter_id=user_id)

        return jsonify({
            'status': "success",
            'message':"文件删除成功"
        })
    except Exception as e:
        return jsonify({
            'status': "error",
            'message': f"文件删除失败{str(e)}"
        })

@bp.route('/password_change',methods=['POST'],endpoint='password_change')
@jwt_required
def password_change():
    if not request.is_json:
        return jsonify({
            'status': 'error',
            'message': 'Content-Type必须为application/json'
        }), 400

    form=ChangePasswordForm(data=request.get_json())
    if form.validate():
        print("验证通过，处理密码修改逻辑")
        old_password = form.old_password.data
        new_password = form.new_password.data
        try:
            # 查找用户
            user = g.current_user
            if user:
                if check_password_hash(user.password, old_password):
                    # 更新密码
                    user.password = generate_password_hash(new_password)
                    #修改版本号，弃用原来的token
                    user.password_version=user.password_version+1

                    db.session.commit()

                    return jsonify({
                        'status': 'success',
                        'message': '密码重置成功，请使用新密码登录'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message':'旧密码错误'
                    })
            else:
                return jsonify({
                    'status': 'error',
                    'message': "用户信息获取失败"
                })
        except Exception as e:
            db.session.rollback()
            logger.error(str(e))
            return jsonify({
                'status': 'error',
                'message': f'密码修改失败:{str(e)}'
            })
    return jsonify({
        'status': 'error',
        'message': form.errors
    })

@bp.route('/update_username', methods=['POST'])
@jwt_required
def update_username():
    """修改用户名（主键字段）"""
    try:
        # 查找用户
        print('查找用户')
        print(f'当前用户为{g.user_id}')
        user = g.current_user
        if user:
            data = request.get_json()
            if data['username'] == user.username:
                return jsonify({
                    'status': 'error',
                    'message': '新用户名需与旧用户名不同'
                })
            user2=UserModel.query.filter_by(username=data['username']).first()
            if user2:
                return jsonify({
                    'status': 'error',
                    'message': '用户名已存在'
                })
            user.username = data['username']
            db.session.commit()
            return jsonify({
                'status': 'success',
                'message':'用户名修改成功'
            })
        else:
            return jsonify({
                'status': 'error',
                'message':'用户信息获取失败'
            })
    except Exception as e:
        db.session.rollback()
        logger.error(str(e))
        return jsonify({
            'status': 'error',
            'message': f'用户名修改失败:{str(e)}'
        })

@bp.route('/log_out', methods=['POST'],endpoint='log_out')
@jwt_required
def log_out():
    try:
        user = g.current_user
        user.password_version = user.password_version + 1
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message':'退出登录成功'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(str(e))
        return jsonify({
            'status': 'error',
            'message':str(e)
        })