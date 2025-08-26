from langchain_openai import ChatOpenAI
from typing import Any, List, Optional, Dict, Iterator
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult, ChatGenerationChunk
from langchain_core.callbacks import CallbackManagerForLLMRun

class ChatOpenAIWithoutStop(ChatOpenAI):
    """Custom ChatOpenAI that removes stop parameter and handles GPT-5 specific requirements."""
    
    def __init__(self, **kwargs):
        """Initialize with GPT-5 specific settings."""
        # Force streaming to False and temperature to 1 for GPT-5 models
        if "model_name" in kwargs and "gpt-5" in kwargs.get("model_name", "").lower():
            kwargs["streaming"] = False
            kwargs["temperature"] = 1  # GPT-5 only supports temperature=1
        super().__init__(**kwargs)
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        stream: Optional[bool] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Override _generate to remove stop parameter and disable streaming for GPT-5."""
        # Check if using GPT-5 model
        if "gpt-5" in self.model_name.lower():
            # Remove stop parameter for GPT-5
            stop = None
            # Remove stream from kwargs to avoid duplicate parameter
            kwargs.pop("stream", None)
            # Disable streaming
            stream = False
            # Remove stop-related parameters
            kwargs.pop("stop", None)
            kwargs.pop("stop_sequences", None)
        
        # Call parent method with modified parameters
        return super()._generate(messages, stop=stop, run_manager=run_manager, stream=stream, **kwargs)
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        stream: Optional[bool] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Override async _agenerate to remove stop parameter for GPT-5."""
        # Check if using GPT-5 model
        if "gpt-5" in self.model_name.lower():
            stop = None
            kwargs.pop("stream", None)
            stream = False
            kwargs.pop("stop", None)
            kwargs.pop("stop_sequences", None)
        
        return await super()._agenerate(messages, stop=stop, run_manager=run_manager, stream=stream, **kwargs)
    
    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """Override _stream to use non-streaming generation for GPT-5."""
        # For GPT-5, don't stream - use regular generation instead
        if "gpt-5" in self.model_name.lower():
            # Remove stop and stream parameters
            stop = None
            kwargs.pop("stop", None)
            kwargs.pop("stop_sequences", None)
            kwargs.pop("stream", None)
            
            # Call _generate instead of streaming
            result = self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
            # Yield the result as if it were streamed
            # result.generations is a list of generation lists
            if result.generations and len(result.generations) > 0:
                # Get first generation from the first list
                first_gen_list = result.generations[0]
                if isinstance(first_gen_list, list) and len(first_gen_list) > 0:
                    generation = first_gen_list[0]
                else:
                    # If it's not a list, it's already a generation object
                    generation = first_gen_list
                yield ChatGenerationChunk(message=generation.message)
        else:
            # For other models, use normal streaming
            return super()._stream(messages, stop=stop, run_manager=run_manager, **kwargs)
    
    def invoke(
        self,
        input: Any,
        config: Optional[Dict] = None,
        *,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> BaseMessage:
        """Override invoke to remove stop parameter for GPT-5."""
        if "gpt-5" in self.model_name.lower():
            stop = None
            kwargs.pop("stop", None)
            kwargs.pop("stop_sequences", None)
        
        return super().invoke(input, config=config, stop=stop, **kwargs)
    
    def bind(self, **kwargs: Any) -> "ChatOpenAIWithoutStop":
        """Override bind to remove stop parameter for GPT-5."""
        if "gpt-5" in self.model_name.lower():
            kwargs.pop("stop", None)
            kwargs.pop("stop_sequences", None)
        
        return super().bind(**kwargs)