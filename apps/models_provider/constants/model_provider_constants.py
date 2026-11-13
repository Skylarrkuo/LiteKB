"""Provider IDs are persisted in the database. Import only enabled adapters."""
from functools import lru_cache
from importlib import import_module

from common.exception.app_exception import AppApiException
from maxkb.capabilities import EXTENDED_PROVIDERS, LOCAL_MODEL


PROVIDERS = {
    "model_openai_provider": "openai_model_provider.openai_model_provider:OpenAIModelProvider",
    "aliyun_bai_lian_model_provider": "aliyun_bai_lian_model_provider.aliyun_bai_lian_model_provider:AliyunBaiLianModelProvider",
    "model_xiaomi_mimo_provider": "xiaomi_mimo_model_provider.provider:MiMoProvider",
    "model_deepseek_provider": "deepseek_model_provider.deepseek_model_provider:DeepSeekModelProvider",
    "model_vllm_provider": "vllm_model_provider.vllm_model_provider:VllmModelProvider",
    "model_siliconCloud_provider": "siliconCloud_model_provider.siliconCloud_model_provider:SiliconCloudModelProvider",
}

if LOCAL_MODEL:
    PROVIDERS["model_local_provider"] = "local_model_provider.local_model_provider:LocalModelProvider"

if EXTENDED_PROVIDERS:
    PROVIDERS.update({
        "model_azure_provider": "azure_model_provider.azure_model_provider:AzureModelProvider",
        "model_wenxin_provider": "wenxin_model_provider.wenxin_model_provider:WenxinModelProvider",
        "model_ollama_provider": "ollama_model_provider.ollama_model_provider:OllamaModelProvider",
        "model_docker_ai_provider": "docker_ai_model_provider.docker_ai_model_provider:DockerModelProvider",
        "model_kimi_provider": "kimi_model_provider.kimi_model_provider:KimiModelProvider",
        "model_zhipu_provider": "zhipu_model_provider.zhipu_model_provider:ZhiPuModelProvider",
        "model_xf_provider": "xf_model_provider.xf_model_provider:XunFeiModelProvider",
        "model_gemini_provider": "gemini_model_provider.gemini_model_provider:GeminiModelProvider",
        "model_volcanic_engine_provider": "volcanic_engine_model_provider.volcanic_engine_model_provider:VolcanicEngineModelProvider",
        "model_tencent_provider": "tencent_model_provider.tencent_model_provider:TencentModelProvider",
        "model_aws_bedrock_provider": "aws_bedrock_model_provider.aws_bedrock_model_provider:BedrockModelProvider",
        "model_xinference_provider": "xinference_model_provider.xinference_model_provider:XinferenceModelProvider",
        "model_anthropic_provider": "anthropic_model_provider.anthropic_model_provider:AnthropicModelProvider",
        "model_regolo_provider": "regolo_model_provider.regolo_model_provider:RegoloModelProvider",
        "model_minimax_provider": "minimax_model_provider.minimax_model_provider:MiniMaxModelProvider",
    })


@lru_cache(maxsize=None)
def get_provider(provider_id):
    if provider_id not in PROVIDERS:
        raise AppApiException(400, f"Provider {provider_id} is not installed in this LiteKB deployment")
    module, name = PROVIDERS[provider_id].split(":")
    return getattr(import_module(f"models_provider.impl.{module}"), name)()
