tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "Fetches the current date and time",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_location_by_ip",
            "description": "Fetches the current location based on IP address",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_now_playing",
            "description": "Fetches a list of movies currently playing in theaters",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_showtimes",
            "description": "Fetches a list of showtimes for a movie in a specific location",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the movie"
                    },
                    "location": {
                        "type": "string",
                        "description": "The location of the movie"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pick_random_movie",
            "description": "Picks a random movie from the list of currently playing movies",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buy_ticket",
            "description": "Asks the user to confirm the ticket details",
            "parameters": {
                "type": "object",
                "properties": {
                    "theater": {
                        "type": "string",
                        "description": "The name of the theater"
                    },
                    "movie": {
                        "type": "string",
                        "description": "The title of the movie"
                    },
                    "showtime": {
                        "type": "string",
                        "description": "The showtime of the movie"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_ticket_purchase",
            "description": "If the user confirms the ticket details, this function will execute the purchase",
            "parameters": {
                "type": "object",
                "properties": {
                    "theater": {
                        "type": "string",
                        "description": "The name of the theater"
                    },
                    "movie": {
                        "type": "string",
                        "description": "The title of the movie"
                    },
                    "showtime": {
                        "type": "string",
                        "description": "The showtime of the movie"
                    }
                },
                "required": []
            }
        }
    }
]