from flask import Blueprint, g, jsonify, request, Response as StreamingResponse
from models import ProjectSummaryView, ProjectModel
from jwt_utils import jwt_required
from blueprints.project_view_processor import get_project_summary
from blueprints.file_processing.fileprocessor import AsyncFileProcessor
import logging
import time
import asyncio
import json

"""
Python3.11 适配版流式响应
修复：
1. f-string换行语法报错
2. 未使用的import（删除exts.r）
3. 变量作用域隐藏（result重命名）
4. args参数未填
5. 异步生成器类型不兼容
6. 冗余参数清理
"""

bp = Blueprint('files_preview', __name__, url_prefix='/files_preview')
logger = logging.getLogger(__name__)


# 查找单个文件
def select_a_file(project_id):
    user_id = g.user_id
    logger.info(f"开始查找单个文件，项目ID: {project_id}，用户ID: {user_id}")
    project = ProjectModel.query.filter_by(project_id=project_id, is_deleted=False).first()
    if not project:
        return jsonify({'status': 'error', 'message': "文件不存在"})
    if project.user_id != int(user_id):
        return jsonify({'status': 'error', 'message': "无权限查看"})

    results = ProjectSummaryView.get_project_summary(project.project_id)
    return jsonify({'status': 'success', 'message': results})


@bp.route('/select_files', endpoint='select_files')
@jwt_required
def select_files():
    # 可选输入参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    project_type = request.args.get('status', 'all', type=str)
    date = request.args.get('date')
    username = g.current_user.username
    project_id = request.args.get('project_id', type=str)

    if project_id:
        return select_a_file(project_id)
    else:
        return get_project_summary(page, project_type, per_page, date, False, g.user_id)


# ---------------------- 核心修复：异步获取进度 ----------------------
async def get_user_all_progress(current_user_id):
    """
    异步获取用户所有项目进度
    - 修复：变量名改为current_user_id，避免隐藏外部user_id
    - 修复：同步函数传参规范，解决args未填
    - 修复：result变量重命名，避免作用域隐藏
    """
    results = {}
    try:
        afp = AsyncFileProcessor()

        # 同步数据库查询函数（独立定义）
        def sync_get_projects(user_id):
            return ProjectModel.query.filter_by(
                user_id=user_id,
                is_deleted=False
            ).filter(
                ProjectModel.status.in_(['uploading', 'waiting', 'processing'])
            ).all()

        # Python3.11 异步执行同步函数（传参规范）
        projects = await asyncio.get_event_loop().run_in_executor(
            None,
            sync_get_projects,
            current_user_id
        )

        # 遍历处理每个项目进度
        for project in projects:
            if project.status == 'waiting':
                results[project.project_id] = {
                    'project_id': project.project_id,
                    'status': 'waiting',
                    'total_files': 0,
                    'processed_files': 0,
                    'error_files': 0,
                    'is_complete': False
                }
            else:  # uploading/processing
                # 同步进度查询函数
                def sync_get_progress(pid, status):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    progress_res = loop.run_until_complete(
                        afp.view_analysis_progress(pid, status))  # 重命名result→progress_res
                    loop.close()
                    return progress_res

                # 异步执行同步进度查询
                progress_res = await asyncio.get_event_loop().run_in_executor(  # 重命名result→progress_res
                    None,
                    sync_get_progress,
                    project.project_id,
                    project.status
                )

                # 补充统一格式字段
                progress_res['project_id'] = project.project_id
                progress_res['is_complete'] = (
                    (progress_res.get('processed_files', 0) + progress_res.get('error_files', 0) >= progress_res.get(
                        'total_files', 1))
                    if progress_res.get('total_files', 0) > 0
                    else False
                )
                results[project.project_id] = progress_res

    except Exception as e:
        logger.error(f"获取用户 {current_user_id} 进度失败：{str(e)}", exc_info=True)
        results['error'] = {
            'project_id': 'error',
            'status': f'获取进度失败: {str(e)[:50]}',
            'total_files': 0,
            'processed_files': 0,
            'error_files': 0,
            'is_complete': False
        }
    return results


# ---------------------- 异步生成器（修复f-string换行） ----------------------
async def async_progress_generator(user_id):
    """异步生成器：生产进度数据（修复Python3.11 f-string换行报错）"""
    start_time = time.time()
    global_timeout = 300  # 5分钟超时
    interval = 1.0  # 1秒刷新间隔

    # 初始进度（单行f-string，解决换行报错）
    user_progress = await get_user_all_progress(user_id)
    yield f"data: {json.dumps({'code': 200, 'msg': 'success', 'data': {'user_id': user_id, 'progress': user_progress}}, ensure_ascii=False)}\n\n"

    # 循环推送进度
    while True:
        if time.time() - start_time > global_timeout:
            # 超时响应（单行f-string）
            yield f"data: {json.dumps({'code': 408, 'msg': '进度查询超时（5分钟）', 'data': {'user_id': user_id}}, ensure_ascii=False)}\n\n"
            break

        await asyncio.sleep(interval)
        user_progress = await get_user_all_progress(user_id)

        # 最新进度（单行f-string）
        yield f"data: {json.dumps({'code': 200, 'msg': 'success', 'data': {'user_id': user_id, 'progress': user_progress}}, ensure_ascii=False)}\n\n"

        # 判断完成
        active_projects = [
            p for p in user_progress.values()
            if p.get('status') in ['uploading', 'processing'] and p.get('project_id') != 'error'
        ]
        all_complete = all([p.get('is_complete', False) for p in active_projects]) if active_projects else True

        if all_complete:
            # 完成响应（单行f-string）
            yield f"data: {json.dumps({'code': 200, 'msg': '所有项目进度已完成', 'data': {'user_id': user_id}}, ensure_ascii=False)}\n\n"
            break


# ---------------------- 同步包装器（解决类型不兼容） ----------------------
def sync_progress_generator(user_id):
    """同步包装器：将异步生成器转为StreamingResponse兼容的迭代器"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    gen = async_progress_generator(user_id)
    try:
        while True:
            chunk = loop.run_until_complete(gen.__anext__())
            yield chunk.encode('utf-8')  # 转为bytes，解决类型报错
    except StopAsyncIteration:
        loop.close()
        return


# ---------------------- 流式响应视图（最终修复版） ----------------------
@bp.route("/stream/user/progress", endpoint='stream_progress')
@jwt_required
def stream_user_all_progress():
    """
    流式响应接口（修复所有报错）
    - 删除未使用的exts.r导入
    - 清理冗余参数
    - 规范mimetype参数
    """
    user_id = g.user_id
    logger.info(f"用户 {user_id} 开启进度流式查询")

    return StreamingResponse(
        sync_progress_generator(user_id),
        mimetype="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
