"""从环境变量和 Git 忽略的本地 .env 文件加载配置。"""

from datetime import timedelta
import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv


# 显式指定项目路径，让 Web、worker 和数据库迁移加载同一份配置。
# 系统环境变量优先；保留密码中 ${...} 等字符的原始含义。
load_dotenv(Path(__file__).resolve().with_name('.env'), interpolate=False)


def _required_env(name):
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError(f'请在环境变量或本地 .env 中设置 {name}')
    return value


# JWT 配置：仓库中不提供固定签名密钥。
SECRET_KEY = _required_env('SECRET_KEY')
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
SECURITY_KEY = _required_env('SECURITY_KEY')
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
JWT_TOKEN_LOCATION = ['headers']
JWT_HEADER_NAME = 'Authorization'
JWT_HEADER_TYPE = 'Bearer'

# 数据库配置；DATABASE_URL 可覆盖分别配置的连接参数。
hostname = os.environ.get('DB_HOST', 'localhost')
port = int(os.environ.get('DB_PORT', '3306'))
username = os.environ.get('DB_USER', 'app')
password = os.environ.get('DB_PASSWORD', '')
database = os.environ.get('DB_NAME', 'testdb')
DB_URI = os.environ.get('DATABASE_URL') or (
    f'mysql+pymysql://{quote(username, safe="")}:{quote(password, safe="")}'
    f'@{hostname}:{port}/{quote(database, safe="")}?charset=utf8'
)
SQLALCHEMY_DATABASE_URI = DB_URI

# 邮箱配置。
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.qq.com')
MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'true').lower() == 'true'
MAIL_PORT = int(os.environ.get('MAIL_PORT', '465'))
MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or None
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or None
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or MAIL_USERNAME

# Redis 配置；Flask-Redis 实际通过 REDIS_URL 建立连接。
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD') or None
REDIS_ENCODING = os.environ.get('REDIS_ENCODING', 'utf-8')
REDIS_DB = int(os.environ.get('REDIS_DB', '0'))
REDIS_DECODE_RESPONSES = (
    os.environ.get('REDIS_DECODE_RESPONSES', 'true').lower() == 'true'
)
_redis_auth = f':{quote(REDIS_PASSWORD, safe="")}@' if REDIS_PASSWORD else ''
REDIS_URL = os.environ.get('REDIS_URL') or (
    f'redis://{_redis_auth}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
)

# 文件上传配置。
MAX_CONTENT_LENGTH = 1024 * 1024 * 1024
target = os.environ.get('UPLOAD_DIR', './photo')
target_path = os.path.abspath(target)

# GLM 图像分析接口。
analysis_api_url = os.environ.get(
    'ANALYSIS_API_URL',
    'https://open.bigmodel.cn/api/paas/v4/chat/completions'
)
analysis_api_key = os.environ.get('GLM_API_KEY', '')
analysis_model = os.environ.get('ANALYSIS_MODEL', 'GLM-5.3-flash')
analysis_prompt = os.environ.get(
    'ANALYSIS_PROMPT',
    '请用中文描述这张图片中是什么，尽量说明主要对象、场景和可见特征。'
)

# 管理员邮箱以逗号分隔；未配置时不允许注册管理员。
ADMIN_WHITELIST = [
    email.strip()
    for email in os.environ.get('ADMIN_WHITELIST', '').split(',')
    if email.strip()
]

# Redis 队列的最大并行分析数和最长分析时间。
MAX_RUNNING = 10
max_analysis_time = float(os.environ.get('MAX_ANALYSIS_TIME', '10'))
