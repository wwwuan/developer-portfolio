#拓展工具,解决循环引用
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_redis import FlaskRedis
from flask_jwt_extended import JWTManager
import pytz
from datetime import datetime, timedelta


db=SQLAlchemy()
mail=Mail()
r=FlaskRedis()
Jwt=JWTManager()


def utc_to_local(utc_dt):
    if not utc_dt:
        return ''
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)
    local_tz=pytz.timezone('Asia/Shanghai')
    local_dt = utc_dt.astimezone(local_tz)
    return local_dt.strftime('%Y-%m-%d %H:%M:%S')


def local_to_utc(input_date=None):
    """
    简化版本，只支持None、日期字符串和datetime对象
    """
    try:
        if input_date is None:
            target_date = datetime.now()
        elif isinstance(input_date, str):
            target_date = datetime.strptime(input_date, '%Y-%m-%d')
        elif isinstance(input_date, datetime):
            target_date = input_date
        else:
            target_date = datetime.now()  # 默认今天
    except ValueError:
        print(f"输入的日期字符串 '{input_date}' 格式不符合 '%Y-%m-%d'。")
        return datetime.now()

    # 计算时间范围
    day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    # 转换为UTC（东八区→UTC）
    utc_start = day_start - timedelta(hours=8)
    utc_end = day_end - timedelta(hours=8)

    return utc_start, utc_end