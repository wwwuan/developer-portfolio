from flask import Blueprint,jsonify,g,request
from models import ProjectModel,ProjectSummaryView
import logging
from jwt_utils import jwt_required
from exts import local_to_utc
from blueprints.project_view_processor import get_project_summary


logger = logging.getLogger(__name__)

bp=Blueprint('admin_project',__name__,url_prefix='/admin_project')


"""
进行数据查找
"""

def select_a_file(project_id,user_id):
    print("开始查找单个文件")

    project = ProjectModel.query.filter_by(user_id = user_id, project_id=project_id, is_deleted=False).first()

    if not project:
        return jsonify({
            'status': 'error',
            'message': "文件不存在"
        })

    results = ProjectSummaryView.get_project_summary(project.project_id)

    return jsonify({
        'status': 'success',
        'message': results
    })


#按文件情况查找后计数
def get_today_upload_count_status(status=None):
    """
    :param status: 可选输入状态查找
    :return: 返回按日期与状态的计数
    """
    utc_start, utc_end=local_to_utc()

    projects=ProjectModel.query.filter_by(is_deleted=False)

    if status:
        projects=projects.filter_by(status=status)

    count = projects.filter(
        ProjectModel.upload_time >= utc_start,
        ProjectModel.upload_time < utc_end,
    ).count()

    return count or 0

@bp.route('/select_files', endpoint='select_files')
@jwt_required
def select_files():
    # 可选输入参数
    user_id = g.user_id
    page = request.args.get('page', 1, type=int)
    project_type = request.args.get('status', 'all', type=str)
    per_page = request.args.get('per_page', 10, type=int)  # 添加每页数量参数
    date = request.args.get('date')  # 格式：2001-01-01
    project_id = request.args.get('project_id', type=str)
    is_deleted = request.args.get('is_deleted',False, type=bool)
    if project_id:
        return select_a_file(project_id,user_id)
    else:
        return get_project_summary(page, project_type, per_page, date,is_deleted,user_id)


"""数据统计"""

@bp.route('/',endpoint='index')
@jwt_required
def index():
    """
    展示今天的总上传任务数和失败任务数
    :return:
    """
    try:
        count =get_today_upload_count_status()
        count_completed = get_today_upload_count_status(status='completed')
        count_error =get_today_upload_count_status(status='error')
        count_processing =get_today_upload_count_status(status='processing')
        count_waiting =get_today_upload_count_status(status='waiting')
        results={
            'count':count,
            'count_completed':count_completed,
            'count_error':count_error,
            'count_processing':count_processing,
            'count_waiting':count_waiting
        }
        return jsonify({
            'status' :'success',
            'message' :f'今日文件上传情况：{results}'
        })
    except Exception as e:
        print(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

"""
项目的删除与恢复
"""
@bp.route('/project_delete/<project_id>',endpoint='project_delete')
@jwt_required
def project_delete(project_id):
    try:
        project = ProjectModel.query.filter_by(project_id=project_id).first()
        if not project or project.is_deleted:
            return jsonify({
                'status': 'error',
                'message':'文件不存在'
            })
        project.soft_delete(g.user_id, is_admin=True)
        return jsonify({
            'status': 'success',
            'message':'删除成功'
        })
    except Exception as e:
        print(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@bp.route('/project_restore/<project_id>',endpoint='project_restore')
@jwt_required
def project_restore(project_id):
    try:
        project = ProjectModel.query.filter_by(project_id).first()
        if not project:
            return jsonify({
                'status': 'error',
                'message': '文件不存在'
            })
        project.restore()
        return jsonify({
            'status': 'success',
            'message':'恢复成功'
        })
    except Exception as e:
        print(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        })