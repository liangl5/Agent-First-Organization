import os
import argparse
import json
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

RELEVANT_GOALS = ["learning new map strategies", "learning how to communicate and what to communicate to teammates", "learning how to play a specific agent", "learning how to manage economy", "find tips and resources to getting better aim", "becoming more consistent", "learning various game states", "learning how to take duels"]
CHECK_ENGLISH = "Is this conversation in English:\n{conversation}"
CHECK_GOAL = "Here is a conversation between a user and a coach bot:\n{conversation}\nGive a guess as to what the user's goal was during this conversation, explain your reasoning. After that, determine if the goal you picked falls into one of the categories below, explain your reasoning followed by your final answer which should be either 'yes' or 'no'. If you have any uncertanties about the user's goal your answer should be 'no'. Here are the goal categories:\n{goals}"

SUMMARY = "Valorant offers a competitve 5v5 team-based environment where strategy, communication, and individual skill all blend together. In competitive circuits, players are known for amazing technical skill through precise aim, coordination through strategies, communication, and utility usage, and adaptability to unique high-pressure scenarios."
CHECK_CUSTOMER = "Here is a conversation between a human and a coach bot:\n{convo}\nBased on this conversation, do you think that this person leaned how to become better at the game. Explain your reasoning followed by your final answer of yes or no. Here is a summary of the game to help you decide:\n{summary}"
CHECK_ENGAGEMENT = "Here is a conversation between a human and a coach bot:\n{convo}\nBased on this conversation assess whether the user is positively engaged in the conversation and with the chatbot. Answer yes if the user is engaged and no if the user is not engaged. An example of an unengaged user may be one who gives short replies or asks the bot questions that aren't relevant to the game. Err on the side on answering no unless the user is highly engaged in the conversation. We will be reaching out to these users individually later so don't want to expend the effort unless they were very engaged with the chatbot. Explain your reasoning about whether or not the user is engaged followed by your final answer of yes or no."

FULL_PROFILE = """
goal: learning new map strategies, learning how to communicate and what to communicate to teammates, learning how to play a specific agent, learning how to manage economy, find tips and resources to getting better aim, becoming more consistent, learning various game states, learning how to take duels
player_experience: new to FPS genre, played FPS games before, played valorant, played a lot of valorant
persona: casual, neutral, competitive, professional
main_role: controller, duelist, sentinel, initiator
motivation: get better, get better aim, achieve a higher rank, climb to the highest rank, become a professional
"""
GET_CUSTOMER_PROFILE = "Your job is to take conversations between a user and a coach bot then use it to build a customer profile for the user. Each profile contains a user attribute followed by a value for that attribute. Here is a list of all the attributes followed by the posisble values for that attribute:{full_profile}Based on the conversation below, create a user profile for the user. The profile should contain each attribute followed by exactly one of the values given above, if you're not sure what the value for an attribute should be just put 'other'. Explain your reasoning for each attribute followed by the final profile. It should look exactly like the one given above except for each attribute should only have one value. Here is the conversation:\n{convo}\nYour final output should be formatted as follows:\n[REASONING_FOR_EACH_ATTRIBUTE]\nFinal Profile:\n[FINAL_PROFILE_TEXT]\nPut the output in plain text, there should be no markdown or other formatting like that."


client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    organization=os.environ["OPENAI_ORG_ID"]
)

def chatgpt_chatbot(messages, model):
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
    )
    answer = completion.choices[0].message.content.strip()
    return answer

def join_messages(messages):
    message_str = ""
    for message in messages:
        if message['role'] == 'bot_follow_up':
            continue
        message_str += f"{message['role']}: {message['content']}\n"
    return message_str[:-1]

def rule_based_filtering(convos):
    bad_msg_order = False
    final_convos = []
    for convo in convos:
        if convo['user_msg_length'] < 5:
            continue
        for i in range(len(convo['message'])-1):
            if convo['message'][i]['role'] == 'user' and convo['message'][i+1]['role'] == 'user':
                bad_msg_order = True
                break
        
        if bad_msg_order:
            bad_msg_order = False
            continue
        final_convos.append(convo)
    
    return final_convos

def first_pass_model_filtering(convos, model):
    final_convos = []
    for convo in tqdm(convos):
        convo_str = join_messages(convo["message"])
        english_check = chatgpt_chatbot([{'role': 'user', 'content': CHECK_ENGLISH.format(conversation=convo_str)}], model=model)
        if 'no' in english_check:
            continue
        
        goal_guess = chatgpt_chatbot([{'role': 'user', 'content': CHECK_GOAL.format(conversation=convo_str, goals=RELEVANT_GOALS)}], model=model)
        final_answer = goal_guess.split('\n')[-1]
        if 'yes' in final_answer:
            final_convos.append(convo)
    
    return final_convos

def second_pass_model_filtering(convos, model):
    final_convos = []
    for convo in tqdm(convos):
        convo_str = join_messages(convo["message"])        
        engagement_guess = chatgpt_chatbot([{'role': 'user', 'content': CHECK_ENGAGEMENT.format(convo=convo_str)}], model=model)
        final_answer = engagement_guess.split('\n')[-1]
        if 'yes' in final_answer:
            final_convos.append(convo)
    return final_convos

def extract_customer_profile(customer_profile_output):
    split_profile = customer_profile_output.split("Final Profile:\n")
    profile_text = split_profile[-1]
    profile = {}
    for line in profile_text.split('\n'):
        if ':' not in line:
            continue
        key, val = line.split(': ')
        profile[key] = val
    return profile

def get_all_customer_profiles(final_convos, model):
    failed_extractions = 0
    profiles = {}
    for convo in tqdm(final_convos):
        convo_str = join_messages(convo['message'])
        customer_profile_output = chatgpt_chatbot([{'role': 'user', 'content': GET_CUSTOMER_PROFILE.format(full_profile=FULL_PROFILE, convo=convo_str)}], model=model)
        try:
            profile = extract_customer_profile(customer_profile_output)
        except:
            failed_extractions += 1
            print(f'Profile extraction failed. Total failures: {failed_extractions}')
        profile_vals = ','.join(list(profile.values()))
        profiles[profile_vals] = profiles.get(profile_vals, []) + [convo]
    return profiles

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_data_file', type=str)
    parser.add_argument('--filtering_model', type=str, default='gpt-4o-mini')
    parser.add_argument('--extraction_model', type=str, default='gpt-4o')
    parser.add_argument('--output_data_file', type=str, default='profiles.json')
    args = parser.parse_args()

    with open(args.data_file) as f:
        convos = json.load(f)

    rule_filtered_convos = rule_based_filtering(convos)
    model_filtered_convos = first_pass_model_filtering(convos, args.filtering_model)
    filtered_convos = second_pass_model_filtering(convos, args.filtering_model)
    profiles = get_all_customer_profiles(filtered_convos, args.extraction_model)

    with open(args.output_data_file, 'w') as f:
        json.dump(profiles, f, indent=4)