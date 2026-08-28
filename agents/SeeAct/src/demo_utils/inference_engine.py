# -*- coding: utf-8 -*-
# Copyright (c) 2024 OSU Natural Language Processing Group
#
# Licensed under the OpenRAIL-S License;
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.licenses.ai/ai-pubs-open-rails-vz1
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import time

import backoff
import openai
# Legacy OpenAI SDK imports.
from openai.error import (
    APIConnectionError,
    APIError,
    RateLimitError,
    ServiceUnavailableError,
    InvalidRequestError
)

# New OpenAI SDK imports.
# from openai import OpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError, BadRequestError

import base64

import json
import requests
import time
import sys

from PIL import Image
import json_repair
try:
    from data_sender import upload_to_filer, upload_json_to_mongodb, update_key_to_mongodb
    from config_loader import get_llm_profile, load_app_config
except ImportError:
    from src.data_sender import upload_to_filer, upload_json_to_mongodb, update_key_to_mongodb
    from src.config_loader import get_llm_profile, load_app_config

# def safe_print(text):
#     try:
#         print(text)
#     except UnicodeEncodeError:
#         return



def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


class Engine:
    def __init__(self, **kwargs) -> None:
        pass

    def tokenize(self, input):
        return self.tokenizer(input)


class OpenaiEngine(Engine):
    def __init__(
            self,
            api_key=None,
            stop=["\n\n"],
            rate_limit=-1,
            model=None,
            temperature=0,
            base_url=None,
            **kwargs,
    ) -> None:
        """Init an OpenAI GPT/Codex engine

        Args:
            api_key (_type_, optional): Auth key from OpenAI. Defaults to None.
            stop (list, optional): Tokens indicate stop of sequence. Defaults to ["\n"].
            rate_limit (int, optional): Max number of requests per minute. Defaults to -1.
            model (_type_, optional): Model family. Defaults to None.
        """
        if api_key is None:
            _profile_name, default_profile = get_llm_profile(
                profile_selector="standalone_profile"
            )
            api_key = default_profile["api_key"]
            base_url = base_url or default_profile["base_url"]
            model = model or default_profile["model"]
            kwargs = {**default_profile, **kwargs}
        if isinstance(api_key, str):
            self.api_keys = [api_key]
        elif isinstance(api_key, list):
            self.api_keys = api_key
        else:
            raise ValueError("api_key must be a string or list")
        self.stop = stop
        self.temperature = temperature
        self.model = model
        self.base_url = base_url
        self.llm_config = {
            **kwargs,
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
        }

        # convert rate limit to minmum request interval
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit
        self.next_avil_time = [0] * len(self.api_keys)
        self.current_key_idx = 0
        Engine.__init__(self, **kwargs)

    def encode_image(self, image_path):
        with open(self, image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    @backoff.on_exception(
        backoff.expo,
        (APIError, RateLimitError, APIConnectionError, ServiceUnavailableError, InvalidRequestError),
    )
    def generate(self, prompt: list = None, max_new_tokens=4096, temperature=None, model=None, image_path=None,
                 ouput__0=None, turn_number=0, **kwargs):

        # cjg
        cjg_logger_params = kwargs.get("cjg_logger_params", None)
        if cjg_logger_params:
            cjg_logger_dir = cjg_logger_params.get("cjg_logger_dir", None)
            step = cjg_logger_params.get("step", None)
            type = cjg_logger_params.get("type", None)
            llm = cjg_logger_params.get("llm", None)
            task_id = cjg_logger_params.get("task_id", None)
            seaweedfs_root_dir = (
                cjg_logger_params.get("seaweedfs_root_dir")
                or load_app_config()["seaweedfs"]["root_dir"]
            )

            remote_logger_dir = cjg_logger_dir[cjg_logger_dir.find("cjg_logger") + len("cjg_logger\\"):]
            remote_logger_dir = remote_logger_dir[remote_logger_dir.find("/"):]
            remote_logger_dir = f"/{seaweedfs_root_dir}" + remote_logger_dir
        
        llm_config = kwargs.get("llm_config") or self.llm_config
        # print(f"[CJG_DEBUG] llm_config = {llm_config}")
        if llm_config is None:
            raise ValueError("llm_config must be provided")
        
        logger = kwargs.get("logger", None)
        
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        start_time = time.time()
        if (
                self.request_interval > 0
                and start_time < self.next_avil_time[self.current_key_idx]
        ):
            time.sleep(self.next_avil_time[self.current_key_idx] - start_time)
        
        
        # Legacy OpenAI SDK path.
        # openai.api_key = self.api_keys[self.current_key_idx]
        # openai.api_base = self.base_url

        # New OpenAI SDK path with a custom base URL.
        # from openai import OpenAI
        # client = OpenAI(
        #     api_key=self.api_keys[self.current_key_idx],
        #     base_url=self.base_url  # Set a custom URL.
        # )


        prompt0 = prompt[0]
        prompt1 = prompt[1]
        prompt2 = prompt[2]

        if turn_number == 0:    # action generation
            base64_image = encode_image(image_path)
            # Assume one turn dialogue
            prompt1_input = [
                {"role": "system", "content": [{"type": "text", "text": prompt0}]},
                {"role": "user",
                 "content": [{"type": "text", "text": prompt1}, {"type": "image_url", "image_url": {"url":
                                                                                                        f"data:image/jpeg;base64,{base64_image}",
                                                                                                    "detail": "high"},
                                                                 }]},
            ]
            # prompt1_input = [
            #     {"role": "system", "content": prompt0},
            #     {"role": "user",
            #      "content": [{"type": "text", "text": prompt1}, {"type": "image_url", "image_url": {"url":
            #                                                                                             f"data:image/jpeg;base64,{base64_image}",
            #                                                                                         "detail": "high"},
            #                                                      }]},
            # ]

            # print(f"[DEBUG] prompt1 = {prompt1}")

            # Legacy OpenAI SDK path.
            # response1 = openai.ChatCompletion.create(
            #     model=model if model else self.model,
            #     messages=prompt1_input,
            #     max_tokens=max_new_tokens if max_new_tokens else 4096,
            #     temperature=temperature if temperature else self.temperature,
            #     **kwargs,
            # )
            # answer1 = [choice["message"]["content"] for choice in response1["choices"]][0]

            # Legacy HTTP request implementation.
            # headers = {
            #     'Authorization': f'Bearer {self.api_keys[self.current_key_idx]}',
            #     'Content-Type': 'application/json'
            # }

            # payload = json.dumps({
            #     "model": model if model else self.model,
            #     "messages": prompt1_input,
            #     "max_tokens": max_new_tokens if max_new_tokens else 4096,
            #     "temperature": temperature if temperature else self.temperature,
            # })
            
            # try_cnt = 0
            # while try_cnt < 10:
            #     try:
            #         response = requests.post(self.base_url, headers=headers, data=payload).json()
            #         answer1 = response["choices"][0]["message"]["content"]
            #         break
            #     except Exception as e:
            #         # print(f"Request failed: {e}")
            #         logger.error(f"Request failed: {e}")

            #     try_cnt += 1
            #     if try_cnt < 10:
            #         time.sleep(5)  # Retry delay to avoid triggering rate limits.

            # Current HTTP request implementation.
            headers = {
                llm_config.get("auth_header", "Authorization"): (
                    f'{llm_config.get("auth_scheme", "Bearer")} {llm_config["api_key"]}'
                ).strip(),
                'Content-Type': 'application/json'
            }

            payload = json.dumps({
                "model": llm_config["model"],
                "messages": prompt1_input,
                "max_tokens": max_new_tokens if max_new_tokens else 4096,
                "temperature": temperature if temperature else self.temperature,
            })
            
            try_cnt = 0
            while try_cnt < 5:
                try:
                    endpoint = llm_config.get("endpoint", "/chat/completions")
                    request_url = f"{llm_config['base_url'].rstrip('/')}/{endpoint.lstrip('/')}"
                    response = requests.post(
                        request_url,
                        headers=headers,
                        data=payload,
                        params=llm_config.get("query_params"),
                    )
                    print(f"[CJG_DEBUG] response = {response}")
                    response = response.json()
                    print(f"[CJG_DEBUG] response.json() = {response}")
                    answer1 = response["choices"][0]["message"]["content"]
                    break
                except Exception as e:
                    # print(f"Request failed: {e}")
                    logger.error(f"Request failed: {e}")

                try_cnt += 1
                if try_cnt < 5:
                    time.sleep(20 * try_cnt)  # Retry delay to avoid triggering rate limits.

            
            
            # safe_print(f"[DEBUG] answer1 = {answer1}")
            logger.info(f"[DEBUG] answer1 = {answer1}")

            # with open(f"{cjg_logger_dir}/step_{time_step}/begin.png", "wb") as wf:
            #     wf.write(screenshot_bytes)
                    
            # remote_logger_dir = cjg_logger_dir[cjg_logger_dir.find("cjg_logger") + len("cjg_logger"):]
            # logger.info(f"[TODO] send (local){cjg_logger_dir}/step_{time_step}/begin.png to (SeaweedFS Server) {remote_logger_dir}/step_{time_step}/begin.png")

            # Record the complete LLM input and output for SeaweedFS upload.
            # Record key LLM output fields, such as thought, in MongoDB.
            # TODO 4
            if cjg_logger_dir:
                # Save a copy of image_path under cjg_logger_dir.
                Image.open(image_path).save(f"{cjg_logger_dir}/step_{step}/{type}.png")
                
                # logger.info(f"[TODO] send (local){cjg_logger_dir}/step_{step}/{type}.png to (SeaweedFS Server) {remote_logger_dir}/step_{step}/{type}.png")
                # upload_to_filer(f"{cjg_logger_dir}/step_{step}/{type}.png", f"{remote_logger_dir}/step_{step}/{type}.png")

                answer1_obj = json_repair.loads(answer1)

                remove_image_messages = prompt1_input.copy()
                
                filer_url = load_app_config()["seaweedfs"]["filer_url"].rstrip("/")
                save_image_filepath = f"{filer_url}{remote_logger_dir}/step_{step}/{type}.png"
                for j in range(len(remove_image_messages)):
                    for i in range(len(remove_image_messages[j]["content"])):
                        message = remove_image_messages[j]["content"][i]
                        if message["type"] == "image_url":
                            message["image_url"]["url"] = f"data:image/png;base64,image_filepath=\"{save_image_filepath}\""

                with open(f"{cjg_logger_dir}/step_{step}/{type}.json", "w", encoding="utf-8") as wf:
                    query = {
                        "type": cjg_logger_params["type"],
                        "system_prompt": prompt0,
                        "user_prompt": prompt1,
                        "image_filepath_list": [save_image_filepath],
                        "response_text": answer1,
                        "response_text_obj": answer1_obj,
                        "input_obj": {
                            "model": model if model else self.model,
                            "messages": remove_image_messages,
                            "max_tokens": max_new_tokens if max_new_tokens else 4096,
                            "temperature": temperature if temperature else self.temperature,
                        },
                        "output_obj": response
                    }
                    json.dump(query, wf, indent=4, ensure_ascii=False)
                # logger.info(f"[TODO] send (local){cjg_logger_dir}/step_{step}/{type}.json to (SeaweedFS Server) {remote_logger_dir}/step_{step}/{type}.json")
                # upload_to_filer(f"{cjg_logger_dir}/step_{step}/{type}.json", f"{remote_logger_dir}/step_{step}/{type}.json")

                # Extract key fields from answer1_obj and store them in MongoDB.
                # This should be the natural-language action generated by action generation.
                logger.info(f"[TODO] send critical information of answer1_obj to MongoDB db/collection")
                # update_key_to_mongodb(
                #     key_name=type,
                #     value_obj={
                #         'output': answer1,
                #         'url': f"http://127.0.0.1:8888{remote_logger_dir}/step_{step}/{type}.json"
                #     },
                #     task_id=task_id,
                #     step=step,
                #     db_name="seeact",
                #     collection_name=llm
                # )

                # Save another copy of image_path under cjg_logger_dir.
                # os.makedirs(f"{cjg_logger_dir}/screenshots/step_{step}", exist_ok=True)
                # Image.open(image_path).save(f"{cjg_logger_dir}/screenshots/step_{step}/{type}.png")

                # answer1_obj = json_repair.loads(answer1)

                # remove_image_messages = prompt1_input.copy()
                
                # save_image_filepath = f"{cjg_logger_dir}/screenshots/step_{step}/{type}.png"
                # for j in range(len(remove_image_messages)):
                #     for i in range(len(remove_image_messages[j]["content"])):
                #         message = remove_image_messages[j]["content"][i]
                #         if message["type"] == "image_url":
                #             message["image_url"]["url"] = f"data:image/png;base64,image_filepath=\"{save_image_filepath}\""

                # with open(f"{cjg_logger_dir}/query.json", "r", encoding="utf-8") as rf:
                #     query_list = json.load(rf)

                # with open(f"{cjg_logger_dir}/query.json", "w", encoding="utf-8") as wf:
                #     if f"step_{step}" not in query_list.keys():
                #         query_list[f"step_{step}"] = []
                #     query = {
                #         "type": cjg_logger_params["type"],
                #         "system_prompt": prompt0,
                #         "user_prompt": prompt1,
                #         "image_filepath_list": [f"{cjg_logger_dir}/screenshots/step_{step}/{type}.png"],
                #         "response_text": answer1,
                #         "response_text_obj": answer1_obj,
                #         "input_obj": {
                #             "model": model if model else self.model,
                #             "messages": remove_image_messages,
                #             "max_tokens": max_new_tokens if max_new_tokens else 4096,
                #             "temperature": temperature if temperature else self.temperature,
                #         },
                #         "output_obj": response
                #     }
                #     query_list[f"step_{step}"].append(query)
                #     json.dump(query_list, wf, indent=4, ensure_ascii=False)


            return answer1

            # New OpenAI SDK path.
            # response1 = client.chat.completions.create(
            #     model=model if model else self.model,
            #     messages=prompt1_input,
            #     max_tokens=max_new_tokens if max_new_tokens else 4096,
            #     temperature=temperature if temperature else self.temperature,
            #     **kwargs,
            # )
            # answer1 = response1.choices[0].message.content
        elif turn_number == 1:  # action grounding
            base64_image = encode_image(image_path)
            prompt2_input = [
                {"role": "system", "content": [{"type": "text", "text": prompt0}]},
                {"role": "user",
                 "content": [{"type": "text", "text": prompt1}, {"type": "image_url", "image_url": {"url":
                                                                                                        f"data:image/jpeg;base64,{base64_image}",
                                                                                                    "detail": "high"}, }]},
                {"role": "assistant", "content": [{"type": "text", "text": f"\n\n{ouput__0}"}]},
                {"role": "user", "content": [{"type": "text", "text": prompt2}]}, ]
            # Legacy OpenAI SDK path.
            # response2 = openai.ChatCompletion.create(
            #     model=model if model else self.model,
            #     messages=prompt2_input,
            #     max_tokens=max_new_tokens if max_new_tokens else 4096,
            #     temperature=temperature if temperature else self.temperature,
            #     **kwargs,
            # )
            # return [choice["message"]["content"] for choice in response2["choices"]][0]

            # Legacy HTTP request implementation.
            # headers = {
            #     'Authorization': f'Bearer {self.api_keys[self.current_key_idx]}',
            #     'Content-Type': 'application/json'
            # }

            # payload = json.dumps({
            #     "model": model if model else self.model,
            #     "messages": prompt2_input,
            #     "max_tokens": max_new_tokens if max_new_tokens else 4096,
            #     "temperature": temperature if temperature else self.temperature,
            # })
            
            # try_cnt = 0
            # while try_cnt < 10:
            #     try:
            #         response = requests.post(self.base_url, headers=headers, data=payload).json()
            #         answer2 = response["choices"][0]["message"]["content"]
            #         break
            #     except Exception as e:
            #         # print(f"Request failed: {e}")
            #         logger.error(f"Request failed: {e}")

            #     try_cnt += 1
            #     if try_cnt < 10:
            #         time.sleep(5)  # Retry delay to avoid triggering rate limits.

            # Current HTTP request implementation.
            headers = {
                llm_config.get("auth_header", "Authorization"): (
                    f'{llm_config.get("auth_scheme", "Bearer")} {llm_config["api_key"]}'
                ).strip(),
                'Content-Type': 'application/json'
            }

            payload = json.dumps({
                "model": llm_config["model"],
                "messages": prompt2_input,
                "max_tokens": max_new_tokens if max_new_tokens else 4096,
                "temperature": temperature if temperature else self.temperature,
            })
            
            try_cnt = 0
            while try_cnt < 5:
                try:
                    endpoint = llm_config.get("endpoint", "/chat/completions")
                    request_url = f"{llm_config['base_url'].rstrip('/')}/{endpoint.lstrip('/')}"
                    response = requests.post(
                        request_url,
                        headers=headers,
                        data=payload,
                        params=llm_config.get("query_params"),
                    )
                    print(f"[CJG_DEBUG] response = {response}")
                    response = response.json()
                    print(f"[CJG_DEBUG] response.json() = {response}")
                    answer2 = response["choices"][0]["message"]["content"]

                    break
                except Exception as e:
                    # print(f"Request failed: {e}")
                    logger.error(f"Request failed: {e}")

                try_cnt += 1
                if try_cnt < 5:
                    time.sleep(30 * try_cnt)  # Retry delay to avoid triggering rate limits.
            
            # print(f"[DEBUG] answer2 = {answer2}")
            logger.info(f"[DEBUG] answer2 = {answer2}")
            
            # Record the complete LLM input and output for SeaweedFS upload.
            # Record key LLM output fields, such as thought, in MongoDB.
            # TODO 5
            if cjg_logger_dir:
                # Save a copy of image_path under cjg_logger_dir.
                Image.open(image_path).save(f"{cjg_logger_dir}/step_{step}/{type}.png")
                
                # logger.info(f"[TODO] send (local){cjg_logger_dir}/step_{step}/{type}.png to (SeaweedFS Server) {remote_logger_dir}/step_{step}/{type}.png")
                # upload_to_filer(f"{cjg_logger_dir}/step_{step}/{type}.png", f"{remote_logger_dir}/step_{step}/{type}.png")

                answer2_obj = json_repair.loads(answer2)

                remove_image_messages = prompt2_input.copy()
                
                filer_url = load_app_config()["seaweedfs"]["filer_url"].rstrip("/")
                save_image_filepath = f"{filer_url}{remote_logger_dir}/step_{step}/{type}.png"
                for j in range(len(remove_image_messages)):
                    for i in range(len(remove_image_messages[j]["content"])):
                        message = remove_image_messages[j]["content"][i]
                        if message["type"] == "image_url":
                            message["image_url"]["url"] = f"data:image/png;base64,image_filepath=\"{save_image_filepath}\""

                with open(f"{cjg_logger_dir}/step_{step}/{type}.json", "w", encoding="utf-8") as wf:
                    query = {
                        "type": cjg_logger_params["type"],
                        "system_prompt": prompt0,
                        "user_prompt": prompt2,
                        "image_filepath_list": [save_image_filepath],
                        "response_text": answer2,
                        "response_text_obj": answer2_obj,
                        "input_obj": {
                            "model": model if model else self.model,
                            "messages": remove_image_messages,
                            "max_tokens": max_new_tokens if max_new_tokens else 4096,
                            "temperature": temperature if temperature else self.temperature,
                        },
                        "output_obj": response,
                    }
                    json.dump(query, wf, indent=4, ensure_ascii=False)

                # logger.info(f"[TODO] send (local){cjg_logger_dir}/step_{step}/{type}.json to (SeaweedFS Server) {remote_logger_dir}/step_{step}/{type}.json")
                # upload_to_filer(f"{cjg_logger_dir}/step_{step}/{type}.json", f"{remote_logger_dir}/step_{step}/{type}.json")

                # Extract key fields from answer2_obj and store them in MongoDB.
                # This should be the concrete action produced by action grounding.
                logger.info(f"[TODO] send critical information of answer2_obj to MongoDB db/collection")
                # update_key_to_mongodb(
                #     key_name=type,
                #     value_obj={
                #         'output': answer2,
                #         'url': f"http://127.0.0.1:8888{remote_logger_dir}/step_{step}/{type}.json"
                #     },
                #     task_id=task_id,
                #     step=step,
                #     db_name="seeact",
                #     collection_name=llm
                # )

                # os.makedirs(f"{cjg_logger_dir}/screenshots/step_{step}", exist_ok=True)

                # Save another copy of image_path under cjg_logger_dir.
                # Image.open(image_path).save(f"{cjg_logger_dir}/screenshots/step_{step}/{type}.png")

                # answer2_obj = json_repair.loads(answer2)

                # remove_image_messages = prompt2_input.copy()
                
                # save_image_filepath = f"{cjg_logger_dir}/screenshots/step_{step}/{type}.png"
                # for j in range(len(remove_image_messages)):
                #     for i in range(len(remove_image_messages[j]["content"])):
                #         message = remove_image_messages[j]["content"][i]
                #         if message["type"] == "image_url":
                #             message["image_url"]["url"] = f"data:image/png;base64,image_filepath=\"{save_image_filepath}\""

                # with open(f"{cjg_logger_dir}/query.json", "r", encoding="utf-8") as rf:
                #     query_list = json.load(rf)

                # with open(f"{cjg_logger_dir}/query.json", "w", encoding="utf-8") as wf:
                #     if f"step_{step}" not in query_list.keys():
                #         query_list[f"step_{step}"] = []
                #     query = {
                #         "type": cjg_logger_params["type"],
                #         "system_prompt": "",
                #         "user_prompt": prompt2,
                #         "image_filepath_list": [f"{cjg_logger_dir}/screenshots/step_{step}/{type}.png"],
                #         "response_text": answer2,
                #         "response_text_obj": answer2_obj,
                #         "input_obj": {
                #             "model": model if model else self.model,
                #             "messages": remove_image_messages,
                #             "max_tokens": max_new_tokens if max_new_tokens else 4096,
                #             "temperature": temperature if temperature else self.temperature,
                #         },
                #         "output_obj": response,
                #     }
                #     query_list[f"step_{step}"].append(query)
                #     json.dump(query_list, wf, indent=4, ensure_ascii=False)

            return answer2
            
            # New OpenAI SDK path.
            # response2 = client.chat.completions.create(
            #     model=model if model else self.model,
            #     messages=prompt2_input,
            #     max_tokens=max_new_tokens if max_new_tokens else 4096,
            #     temperature=temperature if temperature else self.temperature,
            #     **kwargs,
            # )
            # return response2.choices[0].message.content


class OpenaiEngine_MindAct(Engine):
    def __init__(
            self,
            api_key=None,
            stop=["\n\n"],
            rate_limit=-1,
            model=None,
            temperature=0,
            **kwargs,
    ) -> None:
        """Init an OpenAI GPT/Codex engine

        Args:
            api_key (_type_, optional): Auth key from OpenAI. Defaults to None.
            stop (list, optional): Tokens indicate stop of sequence. Defaults to ["\n"].
            rate_limit (int, optional): Max number of requests per minute. Defaults to -1.
            model (_type_, optional): Model family. Defaults to None.
        """
        if api_key is None:
            _profile_name, default_profile = get_llm_profile(
                profile_selector="standalone_profile"
            )
            api_key = default_profile["api_key"]
            model = model or default_profile["model"]
        if isinstance(api_key, str):
            self.api_keys = [api_key]
        elif isinstance(api_key, list):
            self.api_keys = api_key
        else:
            raise ValueError("api_key must be a string or list")
        self.stop = stop
        self.temperature = temperature
        self.model = model
        # convert rate limit to minmum request interval
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit
        self.next_avil_time = [0] * len(self.api_keys)
        self.current_key_idx = 0
        Engine.__init__(self, **kwargs)

    @backoff.on_exception(
        backoff.expo,
        (APIError, RateLimitError, APIConnectionError, ServiceUnavailableError),
    )
    def generate(self, prompt, max_new_tokens=50, temperature=0, model=None, **kwargs):
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        start_time = time.time()
        if (
                self.request_interval > 0
                and start_time < self.next_avil_time[self.current_key_idx]
        ):
            time.sleep(self.next_avil_time[self.current_key_idx] - start_time)
        openai.api_key = self.api_keys[self.current_key_idx]
        if isinstance(prompt, str):
            # Assume one turn dialogue
            prompt = [
                {"role": "user", "content": prompt},
            ]
        response = openai.ChatCompletion.create(
            model=model if model else self.model,
            messages=prompt,
            max_tokens=max_new_tokens,
            temperature=temperature,
            **kwargs,
        )
        if self.request_interval > 0:
            self.next_avil_time[self.current_key_idx] = (
                    max(start_time, self.next_avil_time[self.current_key_idx])
                    + self.request_interval
            )
        return [choice["message"]["content"] for choice in response["choices"]]
