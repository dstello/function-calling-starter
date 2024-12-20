import json
from dotenv import load_dotenv
import chainlit as cl
from movie_functions import get_now_playing_movies, get_showtimes, get_current_datetime, get_location_by_ip, buy_ticket, get_reviews
import litellm
from prompts import SYSTEM_PROMPT, RAG_PROMPT
import re
import random
from typing import Dict
from tools import tools
load_dotenv(override=True)

from langsmith import traceable
litellm.success_callback = ["langsmith"] 
litellm.set_verbose=True

# Choose one of these model configurations by uncommenting it:

# OpenAI GPT-4
model = "gpt-4o"
smol_model = "gpt-4o-mini"

# Anthropic Claude
# model = "claude-3-5-sonnet-20241022"
# smol_model = "claude-3-5-haiku-20241022"

# Fireworks Qwen
# model = "fireworks_ai/accounts/fireworks/models/qwen2p5-coder-32b-instruct"

gen_kwargs = {
    "temperature": 0,
    "max_tokens": 500
}

PENDING_PURCHASES: Dict[str, dict] = {}

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

# TODO: this is unused during development, but we should keep it for future use
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
    cl.user_session.set("pending_purchase", None)

@cl.on_message
@traceable
async def on_message(message: cl.Message):
    try:
        message_history = cl.user_session.get("message_history", [])
        message_history.append({"role": "user", "content": message.content})
        
        response_message = cl.Message(content="")
        await response_message.send()

        context_message = get_review_context(message_history)
        if context_message:
            print("Update with review context:", context_message)
            message_history.append(context_message)

        response = litellm.completion(
            model=model,
            messages=message_history,
            tools=tools,
            stream=False,
            **gen_kwargs,
        )
        
        assistant_message = response.choices[0].message
        tool_calls = getattr(assistant_message, 'tool_calls', None)
        print("Received tool calls:", tool_calls)

        if tool_calls:
            available_functions = {
                "get_now_playing": get_now_playing_movies,
                "get_showtimes": get_showtimes,
                "get_current_datetime": get_current_datetime,
                "get_location_by_ip": get_location_by_ip,
                "pick_random_movie": lambda: {"selected_movie": random.choice(get_now_playing_movies()["now_playing_movies"])},
                "buy_ticket": buy_ticket,
                "get_reviews": get_reviews,
            }
            
            message_history.append(assistant_message)

            for tool_call in tool_calls:
                print("Handling tool call:", tool_call)
                function_name = tool_call.function.name
                function_to_call = available_functions.get(function_name)

                if function_to_call:
                    function_args = json.loads(tool_call.function.arguments)
                    print(f"Calling function '{function_name}' with arguments:", function_args)
                    result = function_to_call(**function_args)
                    print(f"Function '{function_name}' returned:", result)
                    
                    message_history.append({
                        "role": "tool",
                        "name": function_name,
                        "content": result,
                        "tool_call_id": tool_call.id 
                    })
                    
            second_response = litellm.completion(
                model=model,
                messages=message_history,
                tools=tools,
                stream=False,
                **gen_kwargs,
            )

            second_response_content = second_response.choices[0].message.content
            if second_response_content is not None:
                await response_message.stream_token(second_response_content)
            else:
                print("Warning: Second response content is None")

        else:
            cleaned_response = assistant_message.content
            print("Assistant response:", cleaned_response)
            await response_message.stream_token(cleaned_response)

        await response_message.update()
        message_history.append({"role": "assistant", "content": response_message.content})
        cl.user_session.set("message_history", message_history)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"An error occurred in on_message: {e}")
        await cl.Message(content="An error occurred while processing your request.").send()

def get_review_context(message_history: list[dict]):
    # Evaluation for fetching movie reviews
    stripped_message_history = [msg for msg in message_history if msg["role"] != "system"]
    review_evaluation_response = litellm.completion(
        model=smol_model,
        messages=stripped_message_history + [{"role": "system", "content": RAG_PROMPT}],
        stream=False,
        **gen_kwargs
    )
    
    review_context = review_evaluation_response.choices[0].message.content
    review_context = json.loads(review_context)
    print("Review Evaluation Result:", review_context)
    
    if review_context.get("fetch_reviews", False):
      reviews = get_reviews(review_context.get("movie"))
      reviews = f"Reviews for {review_context.get('movie')}:\n\n{reviews}"
      context_message = {"role": "user", "content": f"Function call return for get_reviews: {reviews}"}
    else:
      context_message = None
    
    return context_message
    
if __name__ == "__main__":
    cl.main()
