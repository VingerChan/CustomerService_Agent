from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from app.utils.api_caller import call_api
from app.utils.transfer_status import save_transfer_status, remove_transfer_status
from langchain.messages import HumanMessage, AIMessage


@tool
async def transfer_to_human(api: str, method: str, config: RunnableConfig, ai_chat_history: list = None) -> str:
    """
    将当前对话转接给人工客服。

    当用户明确要求转人工客服，或Agent判断无法处理用户问题时使用此工具。
    会创建一个转接会话，返回排队状态信息。

    Args:
        api: API端点路径，从map_user_intent获取，例如 "/api/transfer/create/"
        method: HTTP请求方法，从map_user_intent获取，例如 "POST"
        ai_chat_history: AI与用户的聊天历史（可选），帮助人工客服了解上下文
        config: RunnableConfig，包含用户认证token
    """
    token = config.get('configurable', {}).get('token')
    user_id = config.get('configurable', {}).get('thread_id')
    try:
        from app.main import get_checkpointer
        checkpointer = get_checkpointer()
        chat_history = []
        if checkpointer:
            state = await checkpointer.aget({"configurable": {"thread_id": user_id}})
            if state and 'messages' in state.get('channel_values', {}):
                for msg in state['channel_values']['messages']:
                    if isinstance(msg, HumanMessage):
                        chat_history.append({"role": "user", "content": msg.content})
                    elif isinstance(msg, AIMessage):
                        chat_history.append({"role": "assistant", "content": msg.content})
        result = await call_api(api, token=token, method=method, params={
            'ai_chat_history': chat_history or []
        })
        session_id = result.get('session_id', '')
        status = result.get('status', '')
        queue_position = result.get('queue_position', 0)
        estimated_wait = result.get('estimated_wait_seconds', 0)
        message = result.get('message', '')

        # 保存转人工状态到Redis
        await save_transfer_status(user_id, session_id, status, token)

        return (
            f"转人工请求已提交\n"
            f"会话ID: {session_id}\n"
            f"状态: {status}\n"
            f"排队位置: 第{queue_position}位\n"
            f"预计等待: {estimated_wait}秒\n"
            f"{message}\n\n"
            f"请注意：转人工后，我将退出当前对话，由人工客服接管。"
            f"您可以使用会话ID {session_id} 查询排队进度。"
        )
    except Exception as e:
        return f"转人工请求失败：{str(e)}"


@tool
async def check_transfer_status(api: str, method: str, session_id: str, config: RunnableConfig) -> str:
    """
    查询转人工排队状态。

    当用户想了解转人工排队进度时使用此工具。

    Args:
        api: API端点路径，从map_user_intent获取，例如 "/api/transfer/queue-position/{session_id}/"
        method: HTTP请求方法，从map_user_intent获取，例如 "GET"
        session_id: 转接会话ID
        config: RunnableConfig，包含用户认证token
    """
    token = config.get('configurable', {}).get('token')
    try:
        # 将API路径中的{session_id}替换为实际值
        actual_api = api.replace('{session_id}', session_id)
        result = await call_api(actual_api, token=token, method=method)
        position = result.get('position', 0)
        total = result.get('total_in_queue', 0)
        estimated_wait = result.get('estimated_wait_seconds', 0)
        status = result.get('status', '')
        if status == 'human_active':
            return "人工客服已接入，您可以直接与客服沟通。"
        return (
            f"排队状态查询：\n"
            f"当前位置: 第{position}位\n"
            f"队列总人数: {total}人\n"
            f"预计等待: {estimated_wait}秒\n"
            f"状态: {status}"
        )
    except Exception as e:
        return f"查询排队状态失败：{str(e)}"


@tool
async def send_transfer_message(api: str, method: str, session_id: str, content: str, config: RunnableConfig,message_type: str = 'text') -> str:
    """
    在转人工排队期间发送消息给人工客服。

    当用户在排队中想要留言或补充信息时使用此工具。

    Args:
        api: API端点路径，从map_user_intent获取，例如 "/api/transfer/message/"
        method: HTTP请求方法，从map_user_intent获取，例如 "POST"
        session_id: 转接会话ID
        content: 消息内容
        message_type: 消息类型（text/image/file），默认text
        config: RunnableConfig，包含用户认证token
    """
    token = config.get('configurable', {}).get('token')
    try:
        result = await call_api(api, token=token, method=method, params={
            'session_id': session_id,
            'content': content,
            'message_type': message_type
        })
        return "消息已发送，客服接入后会看到您的留言。"
    except Exception as e:
        return f"发送消息失败：{str(e)}"
