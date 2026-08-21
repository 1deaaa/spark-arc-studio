"""与路由无关的 AI 异常友好化逻辑。"""


# ==================== LLM 错误码四语映射 ====================

# 每条映射格式: (匹配函数, {locale: 友好提示})
# 匹配函数接收原始错误消息(小写)，返回 True 表示命中


def _llm_error_mappings() -> list:
    """返回 LLM 常见错误码的四语友好提示映射表。"""
    return [
        # 401 / authentication_error / auth_unavailable → 鉴权失败
        (
            lambda m: "401" in m or "authentication_error" in m or "auth_unavailable" in m or "invalid_api_key" in m or "invalid x-api-key" in m,
            {
                "zh-CN": "鉴权失败，请检查 API 密钥是否正确填写、是否已过期或被撤销。",
                "en-US": "Authentication failed. Please check if the API key is correct, expired, or revoked.",
                "ja-JP": "認証に失敗しました。API キーが正しく設定されているか、有効期限切れや取り消されていないかご確認ください。",
                "ko-KR": "인증에 실패했습니다. API 키가 올바르게 입력되었는지, 만료되었거나 취소되었는지 확인해 주세요.",
            },
            "401",
        ),
        # 只有提供商明确返回内容安全标记时才归类为内容审计，不能用通用 400 猜测。
        (
            lambda m: (
                "content_filter" in m
                or "content_policy" in m
                or "moderation_blocked" in m
                or "prohibited content" in m
                or ("safety" in m and ("refused" in m or "blocked" in m))
            ),
            {
                "zh-CN": "请求因内容安全策略被提供商拒绝。请根据原始信息检查提示词或输入内容。",
                "en-US": "The provider rejected the request under its content safety policy. Check the prompt or input against the original error details.",
                "ja-JP": "コンテンツ安全ポリシーにより、プロバイダがリクエストを拒否しました。元のエラー情報をもとにプロンプトまたは入力内容をご確認ください。",
                "ko-KR": "콘텐츠 안전 정책에 따라 제공업체가 요청을 거부했습니다. 원본 오류 정보를 바탕으로 프롬프트 또는 입력 내용을 확인해 주세요.",
            },
            "content_policy",
        ),
        # 严格 OpenAI 兼容实现常把工具或结构化输出 Schema 错误返回为 400。
        (
            lambda m: (
                "schema validation" in m
                or "standard_violation" in m
                or "invalid request content" in m
                or ("required" in m and "array" in m)
                or ("invalid-argument" in m and "schema" in m)
            ),
            {
                "zh-CN": "请求参数未通过提供商的 Schema 校验。请检查工具定义、结构化输出、Extra Body 和厂商特定参数是否符合该端点要求。",
                "en-US": "The request failed the provider's schema validation. Check tool definitions, structured output, Extra Body, and provider-specific parameters for this endpoint.",
                "ja-JP": "リクエストパラメータがプロバイダの Schema 検証に失敗しました。ツール定義、構造化出力、Extra Body、プロバイダ固有パラメータをご確認ください。",
                "ko-KR": "요청 매개변수가 제공업체의 Schema 검증을 통과하지 못했습니다. 도구 정의, 구조화 출력, Extra Body 및 제공업체별 매개변수를 확인해 주세요.",
            },
            "schema_validation",
        ),
        # 429 / rate_limit_error → 请求频率限制
        (
            lambda m: "429" in m or "rate_limit" in m or "too_many_requests" in m or "quota_exceeded" in m,
            {
                "zh-CN": "请求过于频繁，已触发提供商速率限制。请等待片刻后重试，或检查您的套餐配额。",
                "en-US": "Too many requests. Rate limit reached. Please wait a moment and retry, or check your plan quota.",
                "ja-JP": "リクエストが多すぎます。レート制限に達しました。しばらく待ってから再試行するか、プランの割り当てをご確認ください。",
                "ko-KR": "요청이 지나치게 빈번하여 제공업체의 속도 제한에 도달했습니다. 잠시 후 다시 시도하거나 요금제 할당량을 확인해 주세요.",
            },
            "429",
        ),
        # 404 + model → 模型不存在
        (
            lambda m: "404" in m and "model" in m,
            {
                "zh-CN": "模型不存在或无法访问。请检查模型名称是否拼写正确，或该模型是否已下线。",
                "en-US": "Model not found or inaccessible. Please verify the model name spelling, or check if the model has been deprecated.",
                "ja-JP": "モデルが存在しないかアクセスできません。モデル名のスペルや、モデルが非公開になっていないかご確認ください。",
                "ko-KR": "모델이 존재하지 않거나 액세스할 수 없습니다. 모델 이름의 철자가 올바른지, 혹은 모델 서비스가 종료되었는지 확인해 주세요.",
            },
            "404",
        ),
        # 500 / internal_server_error → 提供商内部错误
        (
            lambda m: "500" in m or "internal_server_error" in m,
            {
                "zh-CN": "模型提供商内部错误。这通常是提供商侧的临时故障，请稍后重试。",
                "en-US": "Internal server error from the model provider. This is usually a temporary issue on their side. Please retry later.",
                "ja-JP": "モデルプロバイダの内部エラーです。プロバイダ側の一時的な障害であることが多いです。後ほど再試行してください。",
                "ko-KR": "모델 제공업체의 내부 서버 오류입니다. 이는 대개 제공업체 측의 일시적인 장애이므로 나중에 다시 시도해 주세요.",
            },
            "500",
        ),
        # 503 / service_unavailable → 服务不可用
        (
            lambda m: "503" in m or "service_unavailable" in m,
            {
                "zh-CN": "模型提供商服务不可用，通常是由于过载或维护中。请稍后再试。",
                "en-US": "Model provider service unavailable, usually due to overload or maintenance. Please try again later.",
                "ja-JP": "モデルプロバイダのサービスが利用できません。過負荷やメンテナンス中のことが多いです。後ほど再試行してください。",
                "ko-KR": "모델 제공업체 서비스를 이용할 수 없습니다. 대개 서버 과부하 또는 점검 중이므로 나중에 다시 시도해 주세요.",
            },
            "503",
        ),
        # context_length_exceeded / max_context → 上下文超限
        (
            lambda m: "context_length" in m or "max_context" in m or "token_limit" in m or "maximum context" in m,
            {
                "zh-CN": "上下文长度超出模型限制。请尝试缩短输入内容或切换到更大上下文窗口的模型。",
                "en-US": "Context length exceeds model limit. Please try shortening the input or switching to a model with a larger context window.",
                "ja-JP": "コンテキスト長がモデルの制限を超えています。入力を短くするか、より大きなコンテキストウィンドウを持つモデルに切り替えてください。",
                "ko-KR": "컨텍스트 길이가 모델 제한을 초과했습니다. 입력 내용을 줄이거나 더 큰 컨텍스트 창을 지원하는 모델로 전환해 주세요.",
            },
            "context_length",
        ),
        # insufficient_quota → 额度不足
        (
            lambda m: "insufficient_quota" in m or "billing_hard_limit" in m or "quota_exceeded" in m,
            {
                "zh-CN": "API 账户额度不足。请检查您的提供商账户余额或配额。",
                "en-US": "Insufficient API quota. Please check your provider account balance or quota.",
                "ja-JP": "API アカウントのクォータが不足しています。プロバイダのアカウント残高や割り当てをご確認ください。",
                "ko-KR": "API 계정의 잔액 또는 할당량이 부족합니다. 서비스 제공업체 계정의 잔액이나 쿼터를 확인해 주세요.",
            },
            "insufficient_quota",
        ),
        # 其余 400 只说明请求无效，不能臆测为内容审计。
        (
            lambda m: (
                "400" in m
                or "invalid_request_error" in m
                or "invalid argument" in m
                or "invalid-argument" in m
            ),
            {
                "zh-CN": "模型提供商认为请求无效。请根据原始信息检查模型名称、端点协议、工具或结构化输出 Schema、Extra Body 及厂商特定参数。",
                "en-US": "The model provider rejected the request as invalid. Check the model name, endpoint protocol, tool or structured-output schema, Extra Body, and provider-specific parameters against the original error.",
                "ja-JP": "モデルプロバイダがリクエストを無効と判断しました。元のエラー情報をもとに、モデル名、エンドポイントプロトコル、ツールまたは構造化出力の Schema、Extra Body、プロバイダ固有パラメータをご確認ください。",
                "ko-KR": "모델 제공업체가 요청을 유효하지 않은 것으로 판단했습니다. 원본 오류를 바탕으로 모델 이름, 엔드포인트 프로토콜, 도구 또는 구조화 출력 Schema, Extra Body 및 제공업체별 매개변수를 확인해 주세요.",
            },
            "invalid_request",
        ),
        # connection / timeout → 网络连接问题
        (
            lambda m: "timeout" in m or "connection" in m and ("refused" in m or "reset" in m or "timed out" in m),
            {
                "zh-CN": "网络连接异常（超时或拒绝）。请检查网络连接，或确认模型端点地址是否正确。",
                "en-US": "Network connection error (timeout or refused). Please check your network, or verify the model endpoint URL.",
                "ja-JP": "ネットワーク接続エラー（タイムアウトまたは拒否）。ネットワーク接続やモデルエンドポイントの URL をご確認ください。",
                "ko-KR": "네트워크 연결이 비정상적입니다(시간 초과 또는 거부). 네트워크 연결을 확인하거나 모델 엔드포인트 주소가 올바른지 확인해 주세요.",
            },
            "connection",
        ),
    ]


def format_ai_error(e: Exception) -> str:
    """将 AI 生成错误格式化为前端可直接展示的友好文本（四语），尾部附原始报错。"""
    from core.request_context import get_current_locale

    msg = " ".join(str(e).strip().split()) or e.__class__.__name__
    msg_lower = msg.lower()
    locale = get_current_locale()

    # 遍历错误码映射表，命中则返回四语友好提示 + 原始报错
    for matcher, translations, code_tag in _llm_error_mappings():
        if matcher(msg_lower):
            friendly = translations.get(locale, translations["zh-CN"])
            return f"{friendly} (原始信息: {msg})"

    # 默认返回原始错误信息
    return f"[错误: {msg}]"
