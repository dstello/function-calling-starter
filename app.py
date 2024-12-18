import json
from dotenv import load_dotenv
import chainlit as cl
from movie_functions import get_now_playing_movies, get_showtimes
import litellm
from prompts import SYSTEM_PROMPT

load_dotenv(override=True)

from langsmith import traceable
litellm.success_callback = ["langsmith"] 

# Choose one of these model configurations by uncommenting it:

# OpenAI GPT-4
# model = "openai/gpt-4o"

# Anthropic Claude
model = "claude-3-5-sonnet-20241022"

# Fireworks Qwen
# model = "fireworks_ai/accounts/fireworks/models/qwen2p5-coder-32b-instruct"

gen_kwargs = {
    "temperature": 0.2,
    "max_tokens": 500
}

def extract_tag_content(text: str, tag_name: str) -> str | None:
    """
    Extract content between XML-style tags.
    
    Args:
        text: The text containing the tags
        tag_name: Name of the tag to find
        
    Returns:
        String content between tags if found, None if not found
        
    Example:
        >>> text = "before <foo>content</foo> after"
        >>> extract_tag_content(text, "foo")
        'content'
    """
    import re
    pattern = f"<{tag_name}>(.*?)</{tag_name}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else None

def remove_thought_process(text: str) -> str:
    """Remove everything between <thought_process> tags, including the tags"""
    import re
    return re.sub(r'<thought_process>.*?</thought_process>', '', text, flags=re.DOTALL).strip()

@traceable
@cl.on_chat_start
def on_chat_start():    
    message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    cl.user_session.set("message_history", message_history)

@cl.on_message
@traceable
async def on_message(message: cl.Message):
    message_history = cl.user_session.get("message_history", [])
    message_history.append({"role": "user", "content": message.content})
    
    response_message = cl.Message(content="")
    await response_message.send()

    # First LLM call to get function call
    response = litellm.completion(
        model=model,
        messages=message_history,
        stream=False,  # Changed to False for function calling
        **gen_kwargs
    )
    
    # Extract function call if present
    assistant_message = response.choices[0].message
        
    if function_call_text := extract_tag_content(assistant_message.content, "function"):
        # Parse the function call
        function_data = json.loads(function_call_text)
        
        # Execute the function based on the name
        result = None
        if function_data["name"] == "get_now_playing":
            result = get_now_playing_movies()
        elif function_data["name"] == "get_showtimes":
            result = get_showtimes(**function_data.get("arguments", {}))
            
        # Add function result to message history
        if result:
            message_history.append({
                "role": "system",
                "content": f"Function {function_data['name']} returned: {json.dumps(result)}"
            })
            
        # Second LLM call to process function results
        final_response = litellm.completion(
            model=model,
            messages=message_history,
            stream=True,
            **gen_kwargs
        )
        
        # Stream the final response
        for part in final_response:
            chunk_type, content = part
            if content:
                cleaned_content = remove_thought_process(content)
                if cleaned_content:  # Only send if there's content after removing tags
                    await response_message.stream_token(cleaned_content)
    else:
        print("assistant_message.content", assistant_message.content)
        # Clean the original response of thought process tags
        cleaned_response = remove_thought_process(assistant_message.content)
        await response_message.stream_token(cleaned_response)
    
    await response_message.update()
    message_history.append({"role": "assistant", "content": response_message.content})
    cl.user_session.set("message_history", message_history)
    
if __name__ == "__main__":
    cl.main()
