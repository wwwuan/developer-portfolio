from models import ProjectModel, ProjectSummaryView
from flask import jsonify, Response
from exts import local_to_utc

def get_results(projects):
    results = []
    try:
        for project in projects:
            summary = ProjectSummaryView.get_project_summary(project.project_id)
            if summary:
                results.append(summary)
        return results
    except Exception as e:
        print(f'error{str(e)}')
        return []

def get_project_summary(page: object, project_type: object, per_page: object, date: object, is_deleted: object,user_id) -> tuple[Response, int]:
    if page < 1:
        return jsonify({
            'status': 'error',
            'message': '页码输入错误'
        }), 400

    # 构建基础查询
    if project_type == 'all':
        base_query = ProjectModel.get_projects_base_query(desc=True)

        # 补充：过滤软删除（你的模型有is_deleted字段，必须加）        base_query = base_query.filter_by(is_deleted=False)
    else:
        print(project_type)
        # 正确：先过滤，再指定排序字段（如按上传时间降序），最后执行查询
        base_query = ProjectModel.query.filter(
            ProjectModel.status == project_type,  # 状态过滤（关键：project_type 必须是后端认可的值，如 'error'）
            ProjectModel.is_deleted == False  # 过滤已软删除的项目（必加）
        ).order_by(
            ProjectModel.upload_time.desc()  # 按 upload_time 降序排序（desc() 用在字段上）
        ) # 执行查询，返回所有结果列表

    # 添加日期筛选
    if date:
        try:
            utc_start, utc_end = local_to_utc(date)
            base_query = base_query.filter(
                ProjectModel.upload_time >= utc_start,
                ProjectModel.upload_time < utc_end
            )
        except ValueError as e:
            return jsonify({
                'status': 'error',
                'message': f'日期格式错误: {str(e)}'
            }), 400

    # 添加用户名筛选
    if user_id:
        base_query = base_query.filter(ProjectModel.user_id == user_id)

    print("is_deleted",is_deleted)
    if is_deleted:
        print("查找已删除项目")
        base_query = base_query.filter(ProjectModel.deleted == True)

    # 进行分页
    first=base_query.first()
    print(first)

    pagination_result = ProjectModel.paginate_query(
        base_query,
        page=page,
        per_page=per_page
    )

    # 获取项目结果
    results = get_results(pagination_result.items)  # 注意：这里可能也需要改为 .items
    print(pagination_result.page,pagination_result.pages)

    # 修复：使用属性访问而不是字典访问
    return jsonify({
        'status': 'success',
        'data': {
            'projects': results,
            'items_per_page': len(results),
            'pagination': {
                'current_page': pagination_result.page,
                'per_page': pagination_result.per_page,
                'total_items': pagination_result.total,
                'total_pages': pagination_result.pages,
                'has_prev': pagination_result.has_prev,
                'has_next': pagination_result.has_next,
                'prev_page': pagination_result.prev_num,
                'next_page': pagination_result.next_num
            }
        }
    }), 200