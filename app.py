import json
from dotenv import load_dotenv
import chainlit as cl
from movie_functions import get_now_playing_movies, get_showtimes, get_current_date, get_location_by_ip
import litellm
from prompts import SYSTEM_PROMPT
import re
import random

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
    "temperature": 0,
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

def remove_thought_process(text: str, is_suppressing: bool) -> tuple[str, bool]:
    # Check if we have an opening tag in this chunk
    has_opening = "<thought_process>" in text
    has_closing = "</thought_process>" in text
    cleaned_text = text
    
    # If we're not dealing with any tags or not suppressing, return the text as is
    if not has_opening and not has_closing and not is_suppressing:
        return (text, False)
    
    # If we have an opening tag but no closing tag, we're suppressing the tags,return only before the opening tag   
    if has_opening and not has_closing:
        return (text.split("<thought_process>")[0], True)
    
    # if we have a closing tag, keep everything after it
    if has_closing:
        parts = text.split("</thought_process>")
        return (parts[-1], False)  # Return everything after the last closing tag
    
    # If we're currently suppressing and no closing tag found
    if is_suppressing:
        return ("", True)
        
    # Default case
    return (text, False)


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

    is_suppressing = False  # Initialize suppression state

    while True:
        response = litellm.completion(
            model=model,
            messages=message_history,
            stream=False,  # Changed to False for function calling
            **gen_kwargs
        )
        
        assistant_message = response.choices[0].message
        
        if function_call_text := extract_tag_content(assistant_message.content, "function_call"):
            # Parse the function call
            function_data = json.loads(function_call_text)
            
            # Execute the function based on the name
            result = None
            if function_data["name"] == "get_now_playing":
                result = get_now_playing_movies()
            elif function_data["name"] == "get_showtimes":
                result = get_showtimes(**function_data.get("arguments", {}))
            elif function_data["name"] == "get_current_date":
                result = get_current_date()
            elif function_data["name"] == "get_location_by_ip":
                result = get_location_by_ip()
            elif function_data["name"] == "pick_random_movie":
                movies = get_now_playing_movies()
                if movies:
                    result = {"selected_movie": random.choice(movies)}
            # Add more function handlers as needed
                
            print("result", result)
            
            # Add function result to message history
            if result:
                message_history.append({
                    "role": "user",
                    "content": f"Function {function_data['name']} returned: {json.dumps(result)}"
                })
                
            # Update the session with the new history
            cl.user_session.set("message_history", message_history)
        else:
            # No more function calls, process the final response
            cleaned_response = assistant_message.content
            await response_message.stream_token(cleaned_response)
            break  # Exit the loop as there are no more function calls

    await response_message.update()
    message_history.append({"role": "assistant", "content": response_message.content})
    cl.user_session.set("message_history", message_history)
    
if __name__ == "__main__":
    cl.main()
