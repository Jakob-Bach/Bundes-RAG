from typing import Annotated

from fastapi import Depends, Request
from langchain_chroma import Chroma

from bundesrag.config import Settings
from bundesrag.dip.client import DipClient
from bundesrag.query_agent.agent import QueryAgent, create_query_agent
from bundesrag.rag.answer_agent import ChatLlm, create_chat_llm
from bundesrag.vectorstore import get_vectorstore
from bundesrag.web.jobs import JobManager


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_job_manager(request: Request) -> JobManager:
    return request.app.state.job_manager


SettingsDep = Annotated[Settings, Depends(get_settings)]
JobManagerDep = Annotated[JobManager, Depends(get_job_manager)]


def get_dip_client(settings: SettingsDep) -> DipClient:
    return DipClient(api_key=settings.dip_api_key)


def get_query_agent(settings: SettingsDep) -> QueryAgent:
    return create_query_agent(settings)


def get_vectorstore_dep(settings: SettingsDep) -> Chroma:
    return get_vectorstore(settings)


def get_chat_llm(settings: SettingsDep) -> ChatLlm:
    return create_chat_llm(settings)


DipClientDep = Annotated[DipClient, Depends(get_dip_client)]
QueryAgentDep = Annotated[QueryAgent, Depends(get_query_agent)]
VectorstoreDep = Annotated[Chroma, Depends(get_vectorstore_dep)]
ChatLlmDep = Annotated[ChatLlm, Depends(get_chat_llm)]
