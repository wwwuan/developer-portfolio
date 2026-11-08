from flask import Blueprint,jsonify,g
from models import UserModel
import logging
from jwt_utils import jwt_required_admin


logger = logging.getLogger(__name__)

bp=Blueprint('admin_user',__name__,url_prefix='/admin_user')


@bp.route('/user_select/<username>',endpoint='user_select')
@jwt_required_admin
def user_select(username):
    try:
        user=UserModel.query.filter_by(username=username).first()
        if user is None:
            return jsonify({
                'status': 'error',
                'message':'用户名不存在'
            })
        data={
            'username': user.username,
            'email': user.email,
            'status': user.status,
            'create_time': user.create_time
        }
        return jsonify({
            'status': 'success',
            'message': data
        })
    except Exception as e:
        logger.error(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@bp.route('/user_delete/<username>',methods=['GET'],endpoint='admin_user_delete')
@jwt_required_admin
def user_delete(username):
    try:
        user = UserModel.query.filter_by(username=username,status='active').first()
        if user is None:
            return jsonify({
                'status': 'error',
                'message':"用户不存在"
            })
        user.soft_delete(g.user_id,is_admin=True)
        return jsonify({
            'status': 'success',
            'message':"用户删除成功"
        })

    except Exception as e:
        logger.error(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        })


@bp.route('/user_restore/<username>', methods=['GET'], endpoint='admin_user_restore')
@jwt_required_admin
def user_restore(username):
    try:
        user = UserModel.query.filter_by(username=username,is_deleted=True).first()
        if user is None:
            return jsonify({
                'status': 'error',
                'message': "用户不存在"
            })
        user.restore()
        return jsonify({
            'status': 'success',
            'message': "用户恢复成功"
        })

    except Exception as e:
        logger.error(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        })