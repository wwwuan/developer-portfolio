from flask import Blueprint,jsonify,request
from exts import r
import logging
from jwt_utils import jwt_required_admin
from models import UserModel

logger = logging.getLogger(__name__)

bp=Blueprint('admin_error',__name__,url_prefix='/admin_error')

@bp.route("/waiting_project_error",methods=['GET'],endpoint='admin_waiting_project_error')
@jwt_required_admin
def waiting_project_error():
    username= request.args.get('username',None)
    try:
        if username is None:
            keys_count=r.keys("user_id:*:count")
            keys_list=r.keys("user_id:*:waiting_image_list")
            for key in keys_count:
                r.set(key,0)
            for key in keys_list:
                r.delete(key)
        else:
            user=UserModel.query.filter_by(username=username).first()
            if r.get(f"user_id:{user.id}:waiting_image_list") is None:
                r.set(f"user_id:{user.id}:count", 0)
                return jsonify({
                    'status': 'error',
                    'message':'该用户不存在等待处理任务'
                })
        return jsonify({
            'status':'success',
            'message':'处理成功'
        })
    except Exception as e:
        print(f"error:{str(e)}")
        return jsonify({
            'status':'error',
            'message':str(e)
        })