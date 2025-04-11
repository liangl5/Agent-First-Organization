import os
import json
import argparse
import time
import logging
from dotenv import load_dotenv
from pprint import pprint

from arklex.utils.utils import init_logger
from arklex.orchestrator.orchestrator import AgentOrg
from arklex.utils.model_config import MODEL
from arklex.utils.model_provider_config import LLM_PROVIDERS
from arklex.env.env import Env

load_dotenv()

def pprint_with_color(data, color_code="\033[34m"):  # Default to blue
    print(color_code, end="")  # Set the color
    pprint(data)
    print("\033[0m", end="")  


def get_api_bot_response(args, history, user_text, parameters, env):
    data = {"text": user_text, 'chat_history': history, 'parameters': parameters}
    orchestrator = AgentOrg(config=os.path.join(args.input_dir, "taskgraph.json"), env=env)
    result = orchestrator.get_response(data)

    return result['answer'], result['parameters'], result['human_in_the_loop']

def start_premodel_questionaire(path):
    type_map = {
        "int": int,
        "str": str,
        "float": float,
        "bool": bool
    }

    if path != "":
        try:
            with open(path, 'r') as file:
                data = json.load(file)
                
                for question in data['questions']:
                    valid_response = False
                    while not valid_response:
                        user_input = input(question['prompt'])

                        try:
                            conv = type_map[question['type']](user_input)
                            if not question['restricted'] or user_input in question['options']:
                                valid_response = True 
                                os.environ[question['environ_var']] = conv

                        except:
                            valid_response = False
                            print("Incorrect type given")

        except Exception as e:
            raise e
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=str, default="./examples/test")
    parser.add_argument('--model', type=str, default=MODEL["model_type_or_path"])
    parser.add_argument( '--llm-provider',type=str,default=MODEL["llm_provider"],choices=LLM_PROVIDERS)
    parser.add_argument('--log-level', type=str, default="WARNING", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument('--premodel-questionaire', type=str, default="")
    args = parser.parse_args()
    os.environ["DATA_DIR"] = args.input_dir
    MODEL["model_type_or_path"] = args.model
    MODEL["llm_provider"] = args.llm_provider
    log_level = getattr(logging, args.log_level.upper(), logging.WARNING)
    logger = init_logger(log_level=log_level, filename=os.path.join(os.path.dirname(__file__), "logs", "arklex.log"))

    # load premodel questionaire
    # doesn't currently work with evaulation, need to turn off and insert your own data
    start_premodel_questionaire(args.premodel_questionaire)

    config = json.load(open(os.path.join(args.input_dir, "taskgraph.json")))
    env = Env(
        tools = config.get("tools", []),
        workers = config.get("workers", []),
        slotsfillapi = config["slotfillapi"]
    )
        
    history = []
    params = {}
    user_prefix = "user"
    worker_prefix = "assistant"
    for node in config['nodes']:
        if node[1].get("type", "") == 'start':
            start_message = node[1]['attribute']["value"]
            break
    history.append({"role": worker_prefix, "content": start_message})
    pprint_with_color(f"Bot: {start_message}")
    
    while True:
        user_text = input("You: ")
        if user_text.lower() == "quit":
            break
        start_time = time.time()
        output, params, hitl = get_api_bot_response(args, history, user_text, params, env)
        history.append({"role": user_prefix, "content": user_text})
        history.append({"role": worker_prefix, "content": output})
        print(f"getAPIBotResponse Time: {time.time() - start_time}")
        pprint_with_color(f"Bot: {output}")
