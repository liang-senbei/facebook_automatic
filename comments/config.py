"""Facebook 评论系统配置参数"""

# ==================== 账号配额 ====================
DAILY_QUOTA_PER_ACCOUNT = 20
COMMENTS_PER_SESSION_OPTIONS = [3, 4, 5]

# ==================== 时间控制 ====================
WARMUP_DURATION_SEC = (20, 45)
COOLDOWN_DURATION_SEC = (10, 30)
INTER_COMMENT_WAIT_SEC = (15, 35)

# ==================== 并发 ====================
MAX_CONCURRENT_BROWSERS = 5
WORKER_TIMEOUT_SEC = 1800

# ==================== 拟人行为 ====================
RANDOM_ACTION_PROB_EARLY = 0.70
RANDOM_ACTION_PROB_MID = 0.50
RANDOM_ACTION_PROB_LATE = 0.30
LIKE_BEFORE_COMMENT_PROB = 0.60
IDLE_BEFORE_COMMENT_SEC = (3, 8)

# ==================== LLM ====================
COMMENT_LLM_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
COMMENT_LLM_MODELS = [
    "doubao-seed-2-0-lite-260215",
    "doubao-seed-2-0-mini-260215",
    "doubao-seed-2-0-pro-260215",
    "doubao-seed-1-8-251228",
]
COMMENT_LLM_MODEL = COMMENT_LLM_MODELS[0]
COMMENT_LLM_ROTATE = True
COMMENT_LLM_TEMPERATURE = 0.9
COMMENT_LLM_MAX_TOKENS = 500
COMMENT_LLM_CONCURRENCY = 50

# ==================== 重试 ====================
MAX_GENERATE_RETRIES = 2
BATCH_RETRY_ROUNDS = 2
BATCH_RETRY_DELAY = 10
