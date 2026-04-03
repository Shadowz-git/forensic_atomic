import re
import logging
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

from openai import AsyncOpenAI

# Imports for Anthropic
try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None

from config.settings import settings
from core.logger import log

# Global debug flag – set to True to print prompt input, output and token usage
# for every API call across all providers.
LOG_USAGE: bool = True
PRINT_SYSP = False # Log System Prompt
PRINT_USP = False # Log User Prompt
PRINT_OUT = True # Log Output


class UnifiedGenerator:
    """
    Unified handler to call different LLM providers.

    Implementations:
    - OpenRouter: via OpenAI SDK (for Generation)
    - OpenAI: via OpenAI SDK (for Judging/Rewriting)
    - Anthropic: via Anthropic SDK (for Judging)
    - Gemini: via REST API (for Judging, bypasses protobuf issues)
    """

    def __init__(self):
        # OpenRouter Client (Generation)
        if settings.OPENROUTER_API_KEY:
            self.openrouter_client = AsyncOpenAI(
                base_url=settings.OPENROUTER_BASE_URL,
                api_key=settings.OPENROUTER_API_KEY
            )
        else:
            self.openrouter_client = None

        # OpenAI Direct Client (Judge)
        if settings.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            self.openai_client = None

        # Anthropic Direct Client (Judge)
        if AsyncAnthropic and settings.ANTHROPIC_API_KEY:
            self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        else:
            self.anthropic_client = None

        # Gemini Configuration (Judge)
        # We do not use the SDK here to avoid protobuf conflicts.
        self.gemini_key = settings.GEMINI_API_KEY

        log.info("UnifiedGenerator initialized.")

    # Logging helper
    @staticmethod
    def _log_usage(
        provider: str,
        model: str,
        system_prompt: str,
        prompt: str,
        output: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        reasoning_tokens: int | None = None,
        thinking_tokens: int | None = None,
    ) -> None:
        """
        Prints a structured usage report to stdout when LOG_USAGE is True.
        All parameters after `output` are optional and provider-specific.
        """
        if not LOG_USAGE:
            return

        SEP  = "─" * 72
        SEP2 = "═" * 72

        print(f"\n{SEP2}")
        print(f"  PROVIDER : {provider.upper()}  |  MODEL : {model}")
        print(SEP2)

        # Token counts
        parts = []
        if input_tokens  is not None: parts.append(f"input={input_tokens}")
        if output_tokens is not None: parts.append(f"output={output_tokens}")
        if reasoning_tokens is not None and reasoning_tokens > 0:
            parts.append(f"reasoning={reasoning_tokens}")
        if thinking_tokens is not None and thinking_tokens > 0:
            parts.append(f"thinking={thinking_tokens}")
        if parts:
            total = (input_tokens or 0) + (output_tokens or 0)
            parts.append(f"total={total}")
            print(f"  TOKENS   : {' | '.join(parts)}")
            print(SEP)

        # Log System prompt
        if PRINT_SYSP:
            print("  SYSTEM PROMPT:")
            for line in system_prompt.strip().splitlines():
                print(f"    {line}")
            print(SEP)

        # Log User prompt
        if PRINT_USP:
            print("  USER PROMPT:")
            for line in prompt.strip().splitlines():
                print(f"    {line}")
            print(SEP)

        # Log Model output
        if PRINT_OUT:
            print("  OUTPUT:")
            for line in (output or "").strip().splitlines():
                print(f"    {line}")
            print(f"{SEP2}\n")


    def _clean_json(self, text: str) -> str:
        """
        Cleans output from markdown blocks and chain-of-thought tags.
        For models like DeepSeek R1 and Claude Haiku.
        """
        if not text: return ""
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = text.replace("```json", "").replace("```", "").strip()
        return text

    async def _generate_gemini_rest(self, model: str, prompt: str, system_prompt: str) -> str:
        """
        Calls Google Gemini via raw HTTP REST API using aiohttp with thinking mode support.
        This avoids the 'protobuf' version conflict common with google-generativeai SDK.

        Args:
            model: Gemini model name (e.g., 'gemini-3-flash-preview')
            prompt: User prompt/query
            system_prompt: System instructions

        Returns:
            Final text response (thinking blocks are excluded)

        Raises:
            ValueError: If API key is missing or response is malformed
            Exception: If API returns non-200 status
        """
        if not self.gemini_key:
            raise ValueError("Gemini API Key missing in settings.")

        # Ensure model ID has the correct format
        model_id = model if model.startswith("models/") else f"models/{model}"

        url = f"https://generativelanguage.googleapis.com/v1beta/{model_id}:generateContent?key={self.gemini_key}"

        # Construct payload matching Gemini REST API specs
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 800,

                # Thinking configuration for Gemini 3.x models
                "thinkingConfig": {
                    # Options: "MINIMAL"
                    #          "LOW" (~1k thinking tokens, faster)
                    #          "MEDIUM" (~5-10k thinking tokens, balanced)
                    #          "HIGH" (~30k+ thinking tokens, deep reasoning)
                    "thinkingLevel": "MINIMAL"

                    # Alternative (if applicable on the selected model):
                    # "thinkingBudget": 2048  # Range: 0-32768 depending on model
                }
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Gemini API Error {response.status}: {error_text}")

                result = await response.json()

                try:
                    # Extract parts from the response structure
                    parts = result['candidates'][0]['content']['parts']

                    # Separate thinking content (if present) from final text
                    thinking_text = ""
                    final_text = ""

                    for part in parts:
                        if 'text' not in part:
                            continue

                        # Check if this part is marked as thinking/thought
                        # Note: Gemini may use 'thought' flag or other metadata
                        if part.get('thought', False):
                            thinking_text += part['text']
                        else:
                            final_text += part['text']

                    # Fallback: If no explicit final text found, use the last text block
                    # This handles cases where thinking isn't explicitly marked
                    if not final_text and parts:
                        final_text = parts[-1].get('text', '')

                    # Log thinking content for debugging (optional)
                    if thinking_text:
                        log.debug(f"Gemini thinking: {thinking_text[:200]}...")  # First 200 chars

                    # Token usage from usageMetadata
                    usage = result.get("usageMetadata", {})
                    input_tokens    = usage.get("promptTokenCount")
                    output_tokens   = usage.get("candidatesTokenCount")
                    thinking_tokens = usage.get("thoughtsTokenCount")  # Gemini 3.x thinking tokens

                    self._log_usage(
                        provider="gemini",
                        model=model,
                        system_prompt=system_prompt,
                        prompt=prompt,
                        output=final_text,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        thinking_tokens=thinking_tokens,
                    )

                    return final_text

                except (KeyError, IndexError) as e:
                    # Handle safety blocks, empty responses, or unexpected structure
                    log.warning(f"Gemini returned unexpected structure: {result}")
                    raise ValueError(f"Gemini response parsing failed: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(log, logging.WARNING)
    )
    async def generate(self, provider: str, model: str, prompt: str,
                       system_prompt: str = "You are a Forensic Analyst.") -> str:
        """
        Universal generation method. Dispatches the request to the correct client.
        Output is always cleaned of markdown wrappers and CoT tags before returning.

        Args:
            provider: 'openrouter', 'openai', 'anthropic', 'gemini'
            model: Model identifier
            prompt: User input
            system_prompt: System instruction
        """
        output = ""

        try:
            # OPENROUTER (Generation Phase)
            if provider == "openrouter":
                if not self.openrouter_client:
                    raise ValueError("OpenRouter client not configured.")

                response = await self.openrouter_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2048,
                    extra_headers={}
                )

                output = response.choices[0].message.content

                # OpenRouter mirrors OpenAI usage object
                usage = getattr(response, "usage", None)
                self._log_usage(
                    provider="openrouter",
                    model=model,
                    system_prompt=system_prompt,
                    prompt=prompt,
                    output=output,
                    input_tokens=getattr(usage, "prompt_tokens", None),
                    output_tokens=getattr(usage, "completion_tokens", None),
                )

            # OPENAI DIRECT (Judge / Rewriter)
            elif provider == "openai":
                if not self.openai_client:
                    raise ValueError("OpenAI Direct client not configured.")

                # GPT-5 supports reasoning_effort parameter
                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    # Reasoning effort levels: "minimal", "low", "medium" (default), "high"
                    # - minimal: Fastest, least reasoning (~100-500 tokens)
                    # - low: Quick responses, light reasoning (~500-2k tokens)
                    # - medium: Balanced, default level (~2-10k tokens)
                    # - high: Deep reasoning for complex tasks (~10-30k tokens)
                    reasoning_effort="low",
                    max_completion_tokens=800
                )

                # Extract the final response
                # Note: reasoning tokens are separate and not included in message.content
                message = response.choices[0].message
                output  = message.content

                usage = getattr(response, "usage", None)
                reasoning_tokens = None
                if usage and hasattr(usage, "completion_tokens_details"):
                    details = usage.completion_tokens_details
                    reasoning_tokens = getattr(details, "reasoning_tokens", None)

                self._log_usage(
                    provider="openai",
                    model=model,
                    system_prompt=system_prompt,
                    prompt=prompt,
                    output=output,
                    input_tokens=getattr(usage, "prompt_tokens", None),
                    output_tokens=getattr(usage, "completion_tokens", None),
                    reasoning_tokens=reasoning_tokens,
                )

            # ANTHROPIC DIRECT (Judge)
            elif provider == "anthropic":
                if not self.anthropic_client:
                    raise ValueError("Anthropic client not available. Install 'anthropic' package.")

                message = await self.anthropic_client.messages.create(
                    max_tokens=500,       # thinking (≤200) + testo finale (~300)
                    temperature=0.0,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                    model=model,
                )

                text_content     = ""

                for block in message.content:
                    if block.type == "text":
                        text_content = block.text

                output = text_content

                usage = getattr(message, "usage", None)
                # Anthropic exposes thinking tokens inside output_tokens;
                # cache read/write tokens are also available when applicable.
                thinking_tokens = None
                if usage and hasattr(usage, "output_tokens_details"):
                    thinking_tokens = getattr(usage.output_tokens_details, "thinking_tokens", None)

                self._log_usage(
                    provider="anthropic",
                    model=model,
                    system_prompt=system_prompt,
                    prompt=prompt,
                    output=output,
                    input_tokens=getattr(usage, "input_tokens", None),
                    output_tokens=getattr(usage, "output_tokens", None),
                    thinking_tokens=thinking_tokens,
                )

            # GEMINI DIRECT (Judge)
            elif provider == "gemini":
                # Logging is handled inside _generate_gemini_rest
                output = await self._generate_gemini_rest(model, prompt, system_prompt)

            else:
                raise ValueError(f"Unknown provider: {provider}")

        except Exception as e:
            log.error(f"API Call Error [{provider}/{model}]: {str(e)}")
            raise e

        # Single exit point — strips ```json blocks, <think> tags, stray backticks
        # Applies to all providers: Haiku wraps in markdown, DeepSeek uses <think>, etc.
        return self._clean_json(output)