import os
import requests
from serpapi import GoogleSearch
from functools import wraps
from typing import Dict, Any, Callable
from datetime import datetime 

# Global cache dictionary
# Structure: {
#   'function_name:args': response_data
# }
_CACHE: Dict[str, Any] = {}

def memoize_api_call():
    """
    Decorator to memoize API calls
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create a cache key from function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            print(f"\n[CACHE DEBUG] Looking for key: {cache_key}")
            
            # Return cached result if it exists
            if cache_key in _CACHE:
                print(f"[CACHE DEBUG] ✓ Cache hit! Returning cached result")
                return _CACHE[cache_key]
            
            # If no cache, call the function and cache result
            print(f"[CACHE DEBUG] ✗ Cache miss. Calling API and caching result")
            result = func(*args, **kwargs)
            _CACHE[cache_key] = result
            return result
        return wrapper
    return decorator

@memoize_api_call()
def get_current_datetime():
    # format date to Day, Month Day, Year, Hour:Minute:Second
    return datetime.now().strftime("%A, %B %d, %Y %H:%M:%S")

@memoize_api_call()
def get_location_by_ip(ip: str = None) -> str:
    """
    Get approximate location (city, state) using IP address.
    If no IP is provided, gets location for the current machine's public IP.
    Returns location string in format "City, State" or "Location unavailable" on error.
    """
    try:
        # If no IP provided, this will get location based on the requester's IP
        url = f"https://ipapi.co/{ip}/json/" if ip else "https://ipapi.co/json/"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            city = data.get('city', '')
            region = data.get('region', '')
            
            if city and region:
                return f"{city}, {region}"
            return "Location unavailable"
            
        return "Location unavailable"
    except Exception as e:
        print(f"Error getting location: {str(e)}")
        return "Location unavailable"

@memoize_api_call()
def get_now_playing_movies():
    url = "https://api.themoviedb.org/3/movie/now_playing?language=en-US&page=1"
    headers = {
        "Authorization": f"Bearer {os.getenv('TMDB_API_ACCESS_TOKEN')}"
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return f"Error fetching data: {response.status_code} - {response.reason}"
    
    data = response.json()

    movies = data.get('results', [])
    if not movies:
        return "No movies are currently playing."

    formatted_movies = "The TMDb API returned these movies:\n\n"

    for movie in movies:
        title = movie.get('title', 'N/A')
        movie_id = movie.get('id', 'N/A')
        release_date = movie.get('release_date', 'N/A')
        overview = movie.get('overview', 'N/A')
        formatted_movies += (
            f"**Title:** {title}\n"
            f"**Movie ID:** {movie_id}\n"
            f"**Release Date:** {release_date}\n"
            f"**Overview:** {overview}\n\n"
        )

    return formatted_movies

@memoize_api_call()
def get_showtimes(title, location):
    params = {
        "api_key": os.getenv('SERP_API_KEY'),
        "engine": "google",
        "q": f"showtimes for {title}",
        "location": location,
        "google_domain": "google.com",
        "gl": "us",
        "hl": "en"
    }

    print("params", params)
    search = GoogleSearch(params)
    results = search.get_dict()

    if 'showtimes' not in results:
        return f"No showtimes found for {title} in {location}."

    showtimes = results['showtimes'][0]
    formatted_showtimes = f"Showtimes for {title} in {location}:\n\n"

    if showtimes['theaters']:
        theater = showtimes['theaters'][0]
        theater_name = theater.get('name', 'Unknown Theater')
        formatted_showtimes += f"**{theater_name}**\n"

        date = showtimes.get('day', 'Unknown Date')
        formatted_showtimes += f"  {date}:\n"

        for showing in theater.get('showing', []):
            for time in showing.get('time', []):
                formatted_showtimes += f"    - {time}\n"

    formatted_showtimes += "\n"

    return formatted_showtimes

def buy_ticket(theater, movie, showtime):
    return f"Ticket purchased for {movie} at {theater} for {showtime}."

@memoize_api_call()
def get_reviews(movie_title):
    # Get the movie ID from the title
    id_url = f"https://api.themoviedb.org/3/search/movie?query={movie_title}&include_adult=false&language=en-US&page=1"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {os.getenv('TMDB_API_ACCESS_TOKEN')}"
    }

    id_response = requests.get(id_url, headers=headers)
    id_data = id_response.json()
    movie_id = id_data.get('results', [{}])[0].get('id', 'N/A')
    
    if not movie_id:
        return "No movie ID found for the given title."
    
    review_url = f"https://api.themoviedb.org/3/movie/{movie_id}/reviews?language=en-US&page=1"

    response = requests.get(review_url, headers=headers)
    reviews_data = response.json()

    if 'results' not in reviews_data or not reviews_data['results']:
        return "No reviews found."

    formatted_reviews = ""
    for review in reviews_data['results']:
        author = review.get('author', 'N/A')
        rating = review.get('author_details', {}).get('rating', 'N/A')
        content = review.get('content', 'N/A')
        created_at = review.get('created_at', 'N/A')
        url = review.get('url', 'N/A')

        formatted_reviews += (
            f"**Author:** {author}\n"
            f"**Rating:** {rating}\n"
            f"**Content:** {content}\n"
            f"**Created At:** {created_at}\n"
            f"**URL:** {url}\n"
            "----------------------------------------\n"
        )

    return formatted_reviews

def clear_cache():
    """Clear the entire API cache"""
    global _CACHE
    _CACHE = {}

def clear_cache_for_function(function_name: str):
    """Clear cache entries for a specific function"""
    global _CACHE
    _CACHE = {k: v for k, v in _CACHE.items() if not k.startswith(f"{function_name}:")}

def print_cache_status():
    """Print the current contents of the cache"""
    print("\n[CACHE STATUS]")
    print(f"Total cached items: {len(_CACHE)}")
    for key in _CACHE:
        print(f"- {key}")
