print('hihi')
import os
# In your bot's Python script
import os

# Get the API key from the environment variable
api_key = os.environ.get('API_KEY')
api_secret = os.environ.get('API_SECRET')
print(api_key)
if not api_key or not api_secret:
    raise ValueError("API_KEY and API_SECRET environment variables not set!")
