import os
import logging
from typing import List
import pickle
import requests

from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_community.vectorstores.faiss import FAISS
from langchain_openai import OpenAIEmbeddings


from arklex.utils.model_config import MODEL
from arklex.env.prompts import load_prompts
from arklex.utils.graph_state import MessageState
from arklex.utils.model_provider_config import PROVIDER_MAP, PROVIDER_EMBEDDINGS, PROVIDER_EMBEDDING_MODELS
from arklex.env.tools.utils import trace


logger = logging.getLogger(__name__)

class APIEngine():
    @staticmethod
    def api_retrieve(state: MessageState):

        
        #response = requests.get("https://api.henrikdev.xyz/valorant/v3/matches/na/monkeyman101/monke", # Use this one for eval as not sure how to make prequestionaire work
        response = requests.get("https://api.henrikdev.xyz/valorant/v3/matches/"+ os.getenv("VALO_REGION") + "/" + os.getenv("VALO_USERNAME").replace("#", "/"),
            headers={
                "Authorization": os.getenv("VALO_API_KEY"),
            },
            params = {
                "size": "10",
                "mode": "competitive",
            }
        )
        data = response.json()
    
        res = ""
        for i, match in enumerate(data['data']):
            if match['is_available']:
                res += f'Match {i+1}\n'
                res += f"Map: {match['metadata']['map']}, Rounds Played: {match['metadata']['rounds_played']}\n"
                res += f"Red Team won {match['teams']['red']['rounds_won']} rounds, Blue Team won {match['teams']['blue']['rounds_won']} rounds\n\n"
                res += "Players: \n"

                for player in match['players']['all_players']:
                    if player['name']+"#"+player['tag'] == os.getenv("VALO_USERNAME"):
                        res += "User: "
            
                    res += f"{player['team']} Team, Playing as {player['character']}, {player['currenttier_patched']} rank, {player['damage_made']} outgoing damage, {player['damage_received']} damage received, stats {player['stats']}, ability casts {player['ability_casts']}, economy {player['economy']}"
                    
                    res += "\n"
                res += "\n\n"

        state.message_flow = res
        return state
