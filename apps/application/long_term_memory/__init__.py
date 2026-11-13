import re

import uuid_utils.compat as uuid
from django.db.models import QuerySet
from langchain_core.messages import HumanMessage

from application.flow.common import get_base_node_model
from application.models import ChatRecord, Application, ApplicationLongTermMemory
from common.utils.logger import maxkb_logger
from models_provider.tools import get_model_instance_by_model_workspace_id
from ops import celery_app

long_term_prompt = '''
你是一个专业的用户长期记忆提炼引擎。你的唯一职责是：从对话中精确识别具有持久价值的用户信息，并与已有记忆进行结构化融合，输出供 AI 助手长期使用的用户画像记忆。

## 输入
【已有记忆】：
{{existing_memory}}

【本轮新增对话】：
{{new_conversation}}

---

## 提取门槛（必须同时满足，才可提取）

1. **跨会话复用价值**：这条信息在未来其他对话中仍然适用，而非当次临时需求
2. **明确可证**：可从对话原文直接支撑，不得推断、脑补或延伸
3. **改善回答质量**：记住这条信息后，AI 的回答会对该用户更准确或更贴合

**以下内容禁止提取：**
- 用户的一次性临时要求（如「这次用表格输出就好」）
- 用户提问的具体内容本身（问题不是记忆）
- 无法从对话原文直接证明的推断
- 闲聊、问候、感谢等无信息量内容
- AI 的回答内容（只提取用户侧信息）

---

## 四类记忆分类与融合规则

### 【偏好】交互偏好
用户对「AI 如何回应」的稳定期望，需明确声明或在多轮中反复体现才可录入。

常见维度：回答详略 / 语言风格（正式/口语）/ 输出格式（表格/列表/段落）/ 是否要举例 / 代码风格偏好 / 回复语言

融合规则：
- 同维度出现新偏好 → **覆盖**旧值，条目末标注 `※已更新`
- 新维度 → 直接追加
- 旧偏好无新证据但未被否定 → **保留**

---

### 【背景】用户背景
用户的客观身份与环境信息，稳定性强，用户未明确更正则不主动变动。

常见维度：职业/角色 / 所在行业 / 技术栈与熟练度 / 使用产品或系统 / 团队规模 / 所在地区

融合规则：
- 与旧记忆冲突 → **以新对话为准**，标注 `※已更新`，删除旧值
- 新增信息 → 追加
- 信息模糊无法确认 → 追加时标注 `※待确认`

---

### 【约定】明确约定
用户明确要求 AI 固定遵守的行为规则，须有明确指令性语言支撑，不可自行解读。

常见维度：禁止行为 / 固定执行动作 / 特定触发词响应 / 内容边界 / 输出限制

融合规则：
- 同类新规则 → **覆盖**旧规则，标注 `※已更新`
- 新增规则 → 追加
- 用户明确取消的规则 → **直接删除**

---

### 【目标】当前目标
用户近期或长期正在推进的具体目标，有助于 AI 主动提供更相关的帮助。

常见维度：正在进行的项目 / 学习计划 / 待解决的核心问题 / 关键决策

融合规则：
- 已明确完成或放弃的目标 → **删除**
- 新目标 → 追加
- 已有目标有进展更新 → **覆盖**旧描述

---

## 输出规范

1. **只输出记忆内容本身**，不含任何开头语、解释、总结或分隔说明
2. 四个章节**全部输出**，确无内容写「暂无」，不可省略章节
3. 每条格式：`- [维度标签] 内容`，标签 2~5 字，精准简洁
4. 有变更标记（`※已更新` / `※待确认`）的条目置于各章节**最前**
5. 每条记忆控制在 **60 字以内**，信息密度优先，超出则拆为两条
6. 输出语言与【本轮新增对话】主要语言保持一致

---

## 输出格式

### 【偏好】交互偏好
- [维度标签] 内容
（暂无则写：暂无）

### 【背景】用户背景
- [维度标签] 内容
（暂无则写：暂无）

### 【约定】明确约定
- [维度标签] 内容
（暂无则写：暂无）

### 【目标】当前目标
- [维度标签] 内容
（暂无则写：暂无）

'''


def _get_long_term_config(application, chat_user_id):
    """
    提取长期记忆配置，返回 dict 或 None（None 表示不需要提取，已清理记忆）
    """
    if application.type == 'WORK_FLOW':
        node_list = application.work_flow.get('nodes', [])
        base_node = next((n for n in node_list if n.get('id') == 'base-node'), None)
        if base_node is None:
            return None
        node_data = base_node.get('properties', {}).get('node_data', {})
        if not node_data.get('long_term_enable', False):
            QuerySet(ApplicationLongTermMemory).filter(
                application_id=application.id, chat_user_id=chat_user_id
            ).delete()
            return None
        return {
            'trigger_type': node_data.get('long_term_trigger_type'),
            'trigger_setting': node_data.get('long_term_trigger_setting') or {'rounds': 10},
            **get_base_node_model(application, 'LLM'),
        }
    else:
        if not application.long_term_enable:
            QuerySet(ApplicationLongTermMemory).filter(
                application_id=application.id, chat_user_id=chat_user_id
            ).delete()
            return None
        return {
            'trigger_type': application.long_term_trigger_type,
            'trigger_setting': application.long_term_trigger_setting or {'rounds': 10},
            'model_id': application.long_term_model_id,
            'model_params': application.long_term_model_params_setting or {},
        }


def _run_extract(workspace_id, application_id, chat_user_id, config, history_limit=None, since_time=None):
    """
    执行一次长期记忆提取。
    - since_time 不为 None 时：提取该时间点之后产生的对话。
    - 否则按 history_limit 条数限制。
    """
    if since_time is None and (history_limit is None or history_limit <= 0):
        return

    qs = (
        QuerySet(ChatRecord)
        .filter(
            chat__application_id=application_id,
            chat__chat_user_id=chat_user_id,
        )
        .order_by('-create_time')
        .only('problem_text', 'answer_text')
    )

    if since_time is not None:
        history_chat_record = list(qs.filter(create_time__gte=since_time))
    else:
        history_chat_record = list(qs[:history_limit])
    if len(history_chat_record) == 0:
        return

    chat_model = get_model_instance_by_model_workspace_id(
        config['model_id'], workspace_id, **config['model_params']
    )
    if not chat_model:
        return

    long_term_memory = QuerySet(ApplicationLongTermMemory).filter(
        application_id=application_id, chat_user_id=chat_user_id
    ).first()

    existing_memory = long_term_memory.memory if long_term_memory else ''

    # 反转为时间正序（旧→新）
    history_chat_record = list(reversed(history_chat_record))

    new_conversation = '\n'.join(
        line
        for record in history_chat_record
        for line in (f"用户：{record.problem_text}", f"AI：{record.answer_text}")
    )

    content = ''
    for chunk in chat_model.stream([
        HumanMessage(
            content=long_term_prompt
                    .replace('{{existing_memory}}', existing_memory)
                    .replace('{{new_conversation}}', new_conversation)
        )
    ]):
        content += chunk.content

    content = re.sub(r'<think>.*?<\/think>', '', content, flags=re.DOTALL).strip()

    if long_term_memory:
        long_term_memory.memory = content
        long_term_memory.save()
    else:
        ApplicationLongTermMemory(
            id=uuid.uuid7(),
            application_id=application_id,
            chat_user_id=chat_user_id,
            memory=content,
        ).save()


@celery_app.task(name="celery:extract_long_term_memory")
def extract_long_term_memory(workspace_id, application_id, chat_user_id):
    application = Application.objects.filter(id=application_id).first()
    if not application:
        return

    config = _get_long_term_config(application, chat_user_id)
    if config is None:
        return

    trigger_type = config['trigger_type']
    trigger_setting = config['trigger_setting']

    if trigger_type != 'ROUND':
        # 按照时间的，定时任务会处理
        return

    rounds = trigger_setting.get('rounds', 10)
    if rounds <= 0:
        return

    current_rounds = QuerySet(ChatRecord).filter(
        chat__application_id=application_id,
        chat__chat_user_id=chat_user_id,
    ).count()
    maxkb_logger.info(f'extract_long_term_memory: current_rounds={current_rounds}, rounds={rounds}')
    if current_rounds % rounds != 0:
        return

    _run_extract(workspace_id, application_id, chat_user_id, config, history_limit=rounds)


@celery_app.task(name="celery:schedule_extract_long_term_memory")
def schedule_extract_long_term_memory(workspace_id, application_id, enabled, trigger_type, trigger_setting):
    if not enabled:
        QuerySet(ApplicationLongTermMemory).filter(application_id=application_id).delete()
