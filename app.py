import json
from dotenv import load_dotenv
import chainlit as cl
from movie_functions import get_now_playing_movies, get_showtimes, get_current_datetime, get_location_by_ip, buy_ticket, get_reviews
import litellm
from prompts import SYSTEM_PROMPT, RAG_PROMPT
import re
import random
from typing import Dict

load_dotenv(override=True)

from langsmith import traceable
litellm.success_callback = ["langsmith"] 

# Choose one of these model configurations by uncommenting it:

# OpenAI GPT-4
# model = "openai/gpt-4o"

# Anthropic Claude
model = "claude-3-5-sonnet-20241022"
smol_model = "claude-3-5-haiku-20241022"

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
    message_history = cl.user_session.get("message_history", [])
    message_history.append({"role": "user", "content": message.content})
    
    response_message = cl.Message(content="")
    await response_message.send()

    # Evaluation for fetching movie reviews
    # TODO: We don't know the TMDB ID of the movie yet, so we need to fetch it first
    stripped_message_history = [msg for msg in message_history if msg["role"] != "system"]
    review_evaluation_response = litellm.completion(
        model=smol_model,
        messages=stripped_message_history + [{"role": "system", "content": RAG_PROMPT}],
        stream=False,
        **gen_kwargs
    )
    
    review_context = review_evaluation_response.choices[0].message.content
    print("Review Evaluation Result:", review_context)
    review_context = json.loads(review_context)
    if review_context.get("fetch_reviews", False):
      movie_id = review_context.get("id")
      reviews = get_reviews(movie_id)
      reviews = f"Reviews for {review_context.get('movie')} (ID: {movie_id}):\n\n{reviews}"
      context_message = {"role": "user", "content": f"Function call return for get_reviews: {reviews}"}
      message_history.append(context_message)

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
            function_name = function_data["name"]
            
            # Execute the function based on the name
            result = None
            match function_name:
                case "get_now_playing":
                    result = get_now_playing_movies()
                case "get_showtimes":
                    result = get_showtimes(**function_data.get("arguments", {}))
                case "get_current_datetime":
                    result = get_current_datetime()
                case "get_location_by_ip":
                    result = get_location_by_ip()
                case "pick_random_movie":
                    movies = get_now_playing_movies()
                    if movies:
                        result = {"selected_movie": random.choice(movies)}
                case "buy_ticket":
                    # Store the purchase details for confirmation
                    purchase_details = function_data.get("arguments", {})
                    cl.user_session.set("pending_purchase", purchase_details)
                    
                    # Create confirmation message
                    confirmation_msg = (
                        f"Please confirm your ticket purchase:\n\n"
                        f"Movie: {purchase_details.get('movie_title')}\n"
                        f"Theater: {purchase_details.get('theater')}\n"
                        f"Time: {purchase_details.get('showtime')}\n\n"
                        f"Would you like to proceed with the purchase? (Yes/No)"
                    )
                    
                    # Add the confirmation request to the message history
                    message_history.append({
                        "role": "assistant",
                        "content": confirmation_msg
                    })
                    await response_message.stream_token(confirmation_msg)
                    break  # Exit the loop to wait for user confirmation
                case "confirm_ticket_purchase":
                    # double check previous message history for confirmation
                    confirmation_msg = message_history[-1]["content"]
                    if "yes" in confirmation_msg.lower():
                        result = buy_ticket(**function_data.get("arguments", {}))
                    else:
                        result = "Purchase cancelled by user."
                
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
