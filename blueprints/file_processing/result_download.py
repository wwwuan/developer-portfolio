import pandas as pd
from io import BytesIO
from flask import send_file,Blueprint,jsonify
from datetime import datetime
from models import ProjectModel,ImageResultModel
from openpyxl.utils import get_column_letter
from exts import utc_to_local
from jwt_utils import jwt_required

bp=Blueprint('result_download',__name__,url_prefix='/result_download')

def auto_adjust_columns(writer):
    """自动调整所有列的宽度"""
    for sheet_name in writer.sheets:
        worksheet=writer.sheets[sheet_name]

        for column in worksheet.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)

            for cell in column:
                try:
                    # 处理中文字符（中文字符宽度约为英文字符的2倍）
                    cell_value = str(cell.value) if cell.value else ""
                    chinese_count = sum(1 for char in cell_value if '\u4e00' <= char <= '\u9fff')
                    english_count = len(cell_value) - chinese_count
                    total_width = english_count + chinese_count * 2

                    if total_width > max_length:
                        max_length = total_width
                except:
                    pass

            # 设置列宽，增加一些边距
            adjusted_width = (max_length + 2) * 1.2
            worksheet.column_dimensions[column_letter].width = min(adjusted_width, 50)  # 限制最大宽度


def generate_project_excel_report(project_id):
    """
    生成项目处理结果的Excel报告
    """
    # 获取项目基本信息
    try:
        print("开始生成报告")
        project = ProjectModel.query.filter_by(project_id=project_id,is_deleted=False).first()

        # 获取所有图片分析结果
        image_results = ImageResultModel.query.filter_by(project_id=project_id).all()

        # 创建Excel写入器
        output = BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 工作表1：项目概览
            project_overview_data = {
                '项目ID': [project.project_id],
                '压缩包文件名': [project.zip_filename],
                '原始文件名': [project.original_zip_filename or ''],
                '总图片数量': [project.total_files],
                '成功数量': [project.success_count],
                '失败数量': [project.error_count],
                '状态': [project.status],
                '上传时间': [utc_to_local(project.upload_time) if project.upload_time else ''],
                '开始处理时间': [utc_to_local(project.started_at) if project.started_at else ''],
                '完成时间': [utc_to_local(project.completed_at) if project.completed_at else ''],
                '完成率': [
                    f"{(project.success_count + project.error_count) / project.total_files * 100:.2f}%" if project.total_files > 0 else '0%']
            }

            df_overview = pd.DataFrame(project_overview_data)#将字典数据转换为pandas DataFrame
            df_overview.to_excel(writer, sheet_name='项目概览', index=False)#将Dataframe写入指定工作表

            # 工作表2：详细分析结果
            if image_results:
                detailed_data = []
                for img in image_results:
                    # 处理分析结果
                    analysis_info = ""
                    if img.analysis_result:
                        # 根据您的JSON结构自定义格式化
                        try:
                            if isinstance(img.analysis_result, dict):
                                # 示例：假设分析结果包含检测到的对象信息
                                if 'objects' in img.analysis_result:
                                    objects = img.analysis_result['objects']
                                    analysis_info = f"检测到{len(objects)}个对象"
                                elif 'result' in img.analysis_result:
                                    analysis_info = str(img.analysis_result['result'])
                                else:
                                    analysis_info = "分析完成"
                            else:
                                analysis_info = str(img.analysis_result)
                        except:
                            analysis_info = "结果解析错误"

                    detailed_data.append({
                        '图片文件名': img.image_filename,
                        '状态': img.status,
                        '分析结果': analysis_info,
                        '错误信息': img.error_message or '',
                        '分析时间': utc_to_local(img.analyzed_at) if img.analyzed_at else ''
                    })

                df_detailed = pd.DataFrame(detailed_data)
                df_detailed.to_excel(writer, sheet_name='详细结果', index=False)

                # 工作表3：失败图片汇总
                failed_images = [img for img in image_results if img.status == 'failed']
                if failed_images:
                    failed_data = []
                    for img in failed_images:
                        failed_data.append({
                            '图片文件名': img.image_filename,
                            '错误信息': img.error_message or '未知错误',
                            '分析时间': utc_to_local(img.analyzed_at) if img.analyzed_at else ''
                        })

                    df_failed = pd.DataFrame(failed_data)
                    df_failed.to_excel(writer, sheet_name='失败图片', index=False)

            # 工作表4：统计摘要
            status_count = {}
            for img in image_results:
                status_count[img.status] = status_count.get(img.status, 0) + 1

            summary_data = {
                '统计项': ['总图片数', '成功数', '失败数'],
                '数量': [
                    project.total_files,
                    project.success_count,
                    project.error_count
                ],
                '百分比': [
                    '100%',
                    f"{project.success_count / project.total_files * 100:.2f}%" if project.total_files > 0 else '0%',
                    f"{project.error_count / project.total_files * 100:.2f}%" if project.total_files > 0 else '0%'
                ]
            }

            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name='统计摘要', index=False)

            auto_adjust_columns(writer)

        output.seek(0)
        return output, None
    except Exception as e:
        return None, str(e)


def download_project_excel(project_id):
    """
    下载项目Excel报告（用于Flask路由）
    """
    print("下载报告")
    excel_data, error = generate_project_excel_report(project_id)

    if error:
        print(error)
        return jsonify({
            'status': 'error',
            'message': error
        }), 404

    # 获取项目信息用于文件名
    project = ProjectModel.query.filter_by(project_id=project_id).first()
    filename = f"项目报告_{project.project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return send_file(
        excel_data,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


@bp.route('/project/<project_id>/download_excel')
@jwt_required
def download_excel(project_id):
    """下载Excel报告"""
    return download_project_excel(project_id)
