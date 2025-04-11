import logging
import os
from typing import Any, Iterator, Union

from langgraph.graph import StateGraph, START
from langchain_openai import ChatOpenAI

from arklex.env.workers.worker import BaseWorker, register_worker
from arklex.utils.graph_state import MessageState
from arklex.env.tools.utils import ToolGenerator
from arklex.env.tools.valo_api.valo_api import APIEngine
#from arklex.env.tools.valo_api.valo_api import RetrieveEngine
from arklex.utils.model_config import MODEL
from arklex.utils.model_provider_config import PROVIDER_MAP


logger = logging.getLogger(__name__)

# entire structure should be very similar to faiss_rag_worker, just uses an api to get information instead of pkl documents
@register_worker
class ValoAPI(BaseWorker):

    description = "Answer the user's questions and provide coaching based on insights that can be drawn from a player's match history such as stats (which include kills deaths, score, headshot percentage), agent usage, economy, etc. Player account identifiers are already provided."

    def __init__(self,
                 # stream_ reponse is a boolean value that determines whether the response should be streamed or not.
                 # i.e in the case of RagMessageWorker it should be set to false.
                 stream_response: bool = True):
        super().__init__()
        self.action_graph = self._create_action_graph()
        self.llm = PROVIDER_MAP.get(MODEL['llm_provider'], ChatOpenAI)(
            model=MODEL["model_type_or_path"], timeout=30000
        )
        self.stream_response = stream_response

    def choose_tool_generator(self, state: MessageState):
        if self.stream_response and state.is_stream:
            return "stream_tool_generator"
        return "tool_generator"

    def _create_action_graph(self):
        workflow = StateGraph(MessageState)
        # Add nodes for each worker
        #workflow.add_node("val_api", APIEngine.api_retrieve)
        workflow.add_node("val_api", APIEngine.api_retrieve)
        workflow.add_node("tool_generator", ToolGenerator.context_generate)
        workflow.add_node("stream_tool_generator", ToolGenerator.stream_context_generate)

        # Add edges
        workflow.add_edge(START, "val_api")
        workflow.add_conditional_edges("val_api", self.choose_tool_generator)
        return workflow

    def _execute(self, msg_state: MessageState):
        graph = self.action_graph.compile()
        result = graph.invoke(msg_state)
        return result
