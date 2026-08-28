from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar, overload

import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionContentPartTextParam
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.shared.chat_model import ChatModel
from openai.types.shared_params.reasoning_effort import ReasoningEffort
from openai.types.shared_params.response_format_json_schema import JSONSchema, ResponseFormatJSONSchema
from pydantic import BaseModel

from browser_use.llm.base import BaseChatModel
from browser_use.llm.exceptions import ModelProviderError
from browser_use.llm.messages import BaseMessage
from browser_use.llm.openai.serializer import OpenAIMessageSerializer
from browser_use.llm.schema import SchemaOptimizer
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage
from config_loader import get_llm_profile, load_app_config

import json
import requests

from munch import munchify
import base64
import os
from io import BytesIO
from PIL import Image
import json_repair

from data_sender import update_key_to_mongodb
import time

T = TypeVar('T', bound=BaseModel)


@dataclass
class ChatV3(BaseChatModel):
	"""
	A wrapper around V3's chat model.
	"""

	# Model configuration
	model: ChatModel | str

	# Model params
	temperature: float | None = 0.2
	frequency_penalty: float | None = 0.3  # this avoids infinite generation of \t for models like 4.1-mini
	reasoning_effort: ReasoningEffort = 'low'
	seed: int | None = None
	service_tier: Literal['auto', 'default', 'flex', 'priority', 'scale'] | None = None
	top_p: float | None = None
	add_schema_to_system_prompt: bool = False  # Add JSON schema to system prompt instead of using response_format

	# Client initialization parameters
	api_key: str | None = None
	organization: str | None = None
	project: str | None = None
	base_url: str | httpx.URL | None = None
	websocket_base_url: str | httpx.URL | None = None
	timeout: float | httpx.Timeout | None = None
	max_retries: int = 5  # Increase default retries for automation reliability
	default_headers: Mapping[str, str] | None = None
	default_query: Mapping[str, object] | None = None
	http_client: httpx.AsyncClient | None = None
	_strict_response_validation: bool = False
	max_completion_tokens: int | None = 4096
	reasoning_models: list[ChatModel | str] | None = field(
		default_factory=lambda: [
			'o4-mini',
			'o3',
			'o3-mini',
			'o1',
			'o1-pro',
			'o3-pro',
			'gpt-5',
			'gpt-5-mini',
			'gpt-5-nano',
		]
	)
	llm_config: dict | None = None

	def __post_init__(self) -> None:
		if self.llm_config is None:
			_profile_name, self.llm_config = get_llm_profile()
		self.model = self.llm_config['model']
		self.api_key = self.llm_config['api_key']
		self.base_url = self.llm_config['base_url']

	# Static
	@property
	def provider(self) -> str:
		return 'v3'	

	@property
	def name(self) -> str:
		# return str(self.model)
		return self.llm_config["model_name"]

	def _get_usage(self, response: ChatCompletion) -> ChatInvokeUsage | None:
		try:
			if response.usage is not None:
				completion_tokens = response.usage.completion_tokens
				completion_token_details = response.usage.completion_tokens_details
				if completion_token_details is not None:
					reasoning_tokens = completion_token_details.reasoning_tokens
					if reasoning_tokens is not None:
						completion_tokens += reasoning_tokens

				usage = ChatInvokeUsage(
					prompt_tokens=response.usage.prompt_tokens,
					prompt_cached_tokens=response.usage.prompt_tokens_details.cached_tokens
					if response.usage.prompt_tokens_details is not None
					else None,
					prompt_cache_creation_tokens=None,
					prompt_image_tokens=None,
					# Completion
					completion_tokens=completion_tokens,
					total_tokens=response.usage.total_tokens,
				)
			else:
				usage = None
		except Exception as e:
			print(f"[CJG_DEBUG] _get_usage error: {e}")
			usage = None

		return usage

	@overload
	async def ainvoke(self, messages: list[BaseMessage], output_format: None = None) -> ChatInvokeCompletion[str]: ...

	@overload
	async def ainvoke(self, messages: list[BaseMessage], output_format: type[T]) -> ChatInvokeCompletion[T]: ...

	async def ainvoke(
		self, messages: list[BaseMessage], output_format: type[T] | None = None, **kwargs: Any
	) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:

		cjg_logger_params = kwargs.get('cjg_logger_params', {})
		if cjg_logger_params:
			cjg_logger_dir = cjg_logger_params.get('cjg_logger_dir', None)
			step = cjg_logger_params.get('step', None)
			cjg_task_id = cjg_logger_params.get('cjg_task_id', None)
			cjg_agent_name = cjg_logger_params.get('cjg_agent_name', None)
			seaweedfs_root_dir = (
				cjg_logger_params.get('seaweedfs_root_dir')
				or load_app_config()['seaweedfs']['root_dir']
			)
			cjg_llm = cjg_logger_params.get('cjg_llm', None)
		else:
			cjg_logger_dir = None

		browser_state_summary = kwargs.get('browser_state_summary', None)

		"""
		Invoke the model with the given messages.

		Args:
			messages: List of chat messages
			output_format: Optional Pydantic model class for structured output

		Returns:
			Either a string response or an instance of output_format
		"""

		openai_messages = OpenAIMessageSerializer.serialize_messages(messages)

		try:
			model_params: dict[str, Any] = {}

			if self.temperature is not None:
				model_params['temperature'] = self.temperature

			if self.frequency_penalty is not None:
				model_params['frequency_penalty'] = self.frequency_penalty

			if self.max_completion_tokens is not None:
				model_params['max_completion_tokens'] = self.max_completion_tokens

			if self.top_p is not None:
				model_params['top_p'] = self.top_p

			if self.seed is not None:
				model_params['seed'] = self.seed

			if self.service_tier is not None:
				model_params['service_tier'] = self.service_tier

			if self.reasoning_models and any(str(m).lower() in str(self.model).lower() for m in self.reasoning_models):
				model_params['reasoning_effort'] = self.reasoning_effort
				del model_params['temperature']
				del model_params['frequency_penalty']

			# Structured output is not supported by this custom provider yet.
			output_format = None

			if output_format is None:
				# OpenAI SDK request path.
				# # Return string response
				# response = await self.get_client().chat.completions.create(
				# 	model=self.model,
				# 	messages=openai_messages,
				# 	**model_params,
				# )

				# Legacy HTTP request path.
				# headers = {
				#     'Authorization': f'Bearer {self.v3_api_key}',
				#     'Content-Type': 'application/json'
				# }

				# payload = json.dumps({
				#     "model": self.model,
				#     "messages": openai_messages,
				#     **model_params,
				# })

				# # print(f"[CJG DEBUG] openai_messages: {openai_messages}")

				# try_cnt = 0
				# while try_cnt < 5:
				# 	try:
				# 		response = requests.post(self.v3_base_url, headers=headers, data=payload).json()
				# 		break
				# 	except Exception as e:
				# 		print(f"Request failed: {e}")

				# 	try_cnt += 1
				# 	if try_cnt < 5:
				# 		time.sleep(2)  # Retry delay to avoid triggering rate limits.
				# response = munchify(response)

				# Current HTTP request path.
				if not self.llm_config.get('supports_frequency_penalty', True):
					model_params.pop('frequency_penalty', None)
				
				headers = {
					self.llm_config.get('auth_header', 'Authorization'): (
						f'{self.llm_config.get("auth_scheme", "Bearer")} {self.llm_config["api_key"]}'
					).strip(),
					'Content-Type': 'application/json',
				}

				payload = json.dumps({
				    "model": self.llm_config["model"],
				    "messages": openai_messages,
				    **model_params,
				})

				# print(f"[CJG DEBUG] openai_messages: {openai_messages}")

				# Normal runtime request path.
				call_llm_success = False

				try_cnt = 0
				while try_cnt < 5:
					try:
						endpoint = self.llm_config.get('endpoint', '/chat/completions')
						request_url = f"{self.llm_config['base_url'].rstrip('/')}/{endpoint.lstrip('/')}"
						response = requests.post(request_url, headers=headers, data=payload)
						print(f"[CJG_DEBUG] response = {response}")
						with open(f"{cjg_logger_dir}/step_{step+1}/debug.txt", "a", encoding="utf-8") as wf:
							wf.write(f"[CJG_DEBUG] response = {response}\n")
						response = response.json()
						print(f"[CJG_DEBUG] response.json() = {response}")
						with open(f"{cjg_logger_dir}/step_{step+1}/debug.txt", "a", encoding="utf-8") as wf:
							wf.write(f"[CJG_DEBUG] response.json() = {response}\n")

						response = munchify(response)
						response_text = response.choices[0].message.content
						call_llm_success = True
						break
					except Exception as e:
						print(f"Request failed: {e}")
						with open(f"{cjg_logger_dir}/step_{step+1}/debug.txt", "a", encoding="utf-8") as wf:
							wf.write(f"[CJG_DEBUG] Request failed: {e}\n")

						

					try_cnt += 1
					if try_cnt < 5:
						# time.sleep(20 * try_cnt)  # Retry delay to avoid triggering rate limits.
						time.sleep(5)  # Retry delay to avoid triggering rate limits.

				if call_llm_success == False:
					raise Exception("LLM invocation failed")

				# Debugging only.
				# response = requests.post(f"{self.llm_config['base_url']}/chat/completions", headers=headers, data=payload)
				# print(f"[CJG_DEBUG] response: {response}")
				# response = response.json()
				# print(f"[CJG_DEBUG] response: {response}")
						
				# response = munchify(response)
				
			# 	response = json.loads("""{
            #     "id": "chatcmpl-CTVOH0hStBgmuU53F6nBl7vQQzyyk",
            #     "object": "chat.completion",
            #     "created": 1761148213,
            #     "model": "gpt-4o-2024-08-06",
            #     "choices": [
            #         {
            #             "index": 0,
            #             "message": {
            #                 "role": "assistant",
            #                 "content": "```json\\n{\\n  \\"thoughts\\": \\"The user wants to find a specific paper on arXiv. The best way to achieve this is to go directly to the arXiv website and search for the paper title. The URL for arXiv is arxiv.org.\\",\\n  \\"url\\": \\"https://arxiv.org\\",\\n  \\"title\\": \\"Find Paper on arXiv\\"\\n}\\n```",
            #                 "refusal": null,
            #                 "annotations": []
            #             },
            #             "logprobs": null,
            #             "finish_reason": "stop"
            #         }
            #     ],
            #     "usage": {
            #         "prompt_tokens": 231,
            #         "completion_tokens": 83,
            #         "total_tokens": 314,
            #         "prompt_tokens_details": {
            #             "cached_tokens": 0,
            #             "audio_tokens": 0
            #         },
            #         "completion_tokens_details": {
            #             "reasoning_tokens": 0,
            #             "audio_tokens": 0,
            #             "accepted_prediction_tokens": 0,
            #             "rejected_prediction_tokens": 0
            #         }
            #     },
            #     "system_fingerprint": "fp_4a331a0222"
            # }""")

			# 	response = munchify(response)


				if cjg_logger_dir:
					response_text_obj = json_repair.loads(response_text)

					remove_image_messages = openai_messages.copy()
					
					remote_logger_dir = cjg_logger_dir[cjg_logger_dir.find("cjg_logger") + len("cjg_logger\\"):]
					remote_logger_dir = remote_logger_dir[remote_logger_dir.find("/"):]
					remote_logger_dir = "/" + seaweedfs_root_dir + remote_logger_dir

					filer_url = load_app_config()['seaweedfs']['filer_url'].rstrip('/')
					save_image_filepath = f"{filer_url}{remote_logger_dir}/step_{step+1}/begin.png"
					for j in range(len(remove_image_messages)):
						if isinstance(remove_image_messages[j]["content"], str):
							pass
						else:
							for i in range(len(remove_image_messages[j]["content"])):
								message = remove_image_messages[j]["content"][i]
								if message["type"] == "image_url":
									message["image_url"]["url"] = f"data:image/png;base64,image_filepath=\"{save_image_filepath}\""

					with open(f"{cjg_logger_dir}/step_{step+1}/query.json", "w", encoding="utf-8") as wf:
						query = {
							# "system_prompt": system_prompt,
							# "user_prompt": user_prompt,
							"response_text": response_text,
							"response_text_obj": response_text_obj,
							"input_obj": {
								"model": self.model,
								"messages": remove_image_messages,
								**model_params,
							},
							"output_obj": response
						}
						
						json.dump(query, wf, indent=4, ensure_ascii=False)
					
					try:
						thinking_in_response = response_text_obj["thinking"]
					except Exception as e:
						print(f"[CJG_DEBUG] response_text_obj[\"thinking\"] error: {e}")
						thinking_in_response = ""

					# update_key_to_mongodb(
					# 	key_name="query",
					# 	value_obj={
					# 		'thinking': thinking_in_response,
					# 		'url': f"{filer_url}{remote_logger_dir}/step_{step+1}/query.json"
					# 	},
					# 	task_id=cjg_task_id,
					# 	step=step+1,
					# 	db_name=cjg_agent_name,
					# 	collection_name=cjg_llm
					# )

					# response_text_obj = json_repair.loads(response_text)

					# remove_image_messages = openai_messages.copy()
					
					# save_image_filepath = f"{cjg_logger_dir}/screenshots/step_{step}/begin.png"
					# for j in range(len(remove_image_messages)):
					# 	if isinstance(remove_image_messages[j]["content"], str):
					# 		pass
					# 	else:
					# 		for i in range(len(remove_image_messages[j]["content"])):
					# 			message = remove_image_messages[j]["content"][i]
					# 			if message["type"] == "image_url":
					# 				message["image_url"]["url"] = f"data:image/png;base64,image_filepath=\"{save_image_filepath}\""

					# with open(f"{cjg_logger_dir}/query.json", "r", encoding="utf-8") as rf:
					# 	query_list = json.load(rf)

					# with open(f"{cjg_logger_dir}/query.json", "w", encoding="utf-8") as wf:
					# 	if f"step_{step}" not in query_list.keys():
					# 		query_list[f"step_{step}"] = []
					# 	query = {
					# 		# "system_prompt": system_prompt,
					# 		# "user_prompt": user_prompt,
					# 		"response_text": response_text,
					# 		"response_text_obj": response_text_obj,
					# 		"input_obj": {
					# 			"model": self.model,
					# 			"messages": remove_image_messages,
					# 			**model_params,
					# 		},
					# 		"output_obj": response
					# 	}
					# 	query_list[f"step_{step}"].append(query)
					# 	json.dump(query_list, wf, indent=4, ensure_ascii=False)

					

				
				usage = self._get_usage(response)				
				
				return ChatInvokeCompletion(
					completion=response.choices[0].message.content or '',
					usage=usage,
				)

			else:
				pass
				# response_format: JSONSchema = {
				# 	'name': 'agent_output',
				# 	'strict': True,
				# 	'schema': SchemaOptimizer.create_optimized_json_schema(output_format),
				# }

				# # Add JSON schema to system prompt if requested
				# if self.add_schema_to_system_prompt and openai_messages and openai_messages[0]['role'] == 'system':
				# 	schema_text = f'\n<json_schema>\n{response_format}\n</json_schema>'
				# 	if isinstance(openai_messages[0]['content'], str):
				# 		openai_messages[0]['content'] += schema_text
				# 	elif isinstance(openai_messages[0]['content'], Iterable):
				# 		openai_messages[0]['content'] = list(openai_messages[0]['content']) + [
				# 			ChatCompletionContentPartTextParam(text=schema_text, type='text')
				# 		]

				# # Return structured response
				# response = await self.get_client().chat.completions.create(
				# 	model=self.model,
				# 	messages=openai_messages,
				# 	response_format=ResponseFormatJSONSchema(json_schema=response_format, type='json_schema'),
				# 	**model_params,
				# )

				# if response.choices[0].message.content is None:
				# 	raise ModelProviderError(
				# 		message='Failed to parse structured output from model response',
				# 		status_code=500,
				# 		model=self.name,
				# 	)

				# usage = self._get_usage(response)

				# parsed = output_format.model_validate_json(response.choices[0].message.content)

				# return ChatInvokeCompletion(
				# 	completion=parsed,
				# 	usage=usage,
				# )

		except RateLimitError as e:
			error_message = e.response.json().get('error', {})
			error_message = (
				error_message.get('message', 'Unknown model error') if isinstance(error_message, dict) else error_message
			)
			raise ModelProviderError(
				message=error_message,
				status_code=e.response.status_code,
				model=self.name,
			) from e

		except APIConnectionError as e:
			raise ModelProviderError(message=str(e), model=self.name) from e

		except APIStatusError as e:
			try:
				error_message = e.response.json().get('error', {})
			except Exception:
				error_message = e.response.text
			error_message = (
				error_message.get('message', 'Unknown model error') if isinstance(error_message, dict) else error_message
			)
			raise ModelProviderError(
				message=error_message,
				status_code=e.response.status_code,
				model=self.name,
			) from e

		except Exception as e:
			raise ModelProviderError(message=str(e), model=self.name) from e
