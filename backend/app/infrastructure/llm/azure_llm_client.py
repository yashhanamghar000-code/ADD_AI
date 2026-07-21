from typing import List, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI

from app.core.interfaces.llm_client import ILLMClient


class AzureLlmClient(ILLMClient):
    """Adapter around LangChain's AzureChatOpenAI. Swappable behind
    ILLMClient — an OpenAI-direct or Anthropic client would only need a
    new class here, no changes to any service that calls .complete()."""

    def __init__(self, deployment: str, api_version: str, api_key: str, endpoint: str, temperature: float = 0.1):
        self._llm = AzureChatOpenAI(
            azure_deployment=deployment,
            openai_api_version=api_version,
            api_key=api_key,
            azure_endpoint=endpoint,
            temperature=temperature,
        )

    def complete(self, messages: List[Tuple[str, str]]) -> str:
        lc_messages = []
        for role, content in messages:
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        response = self._llm.invoke(lc_messages)
        return response.content
