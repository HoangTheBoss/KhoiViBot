# Use the Python 3 base image
FROM python:3.10-alpine

# Set the working directory
WORKDIR /app

# Copy the bot repository into the container
COPY . /app

# Install the requirements
RUN pip install -r requirements.txt

# Set the environment variables
ENV OPENAI_API_KEY="your_openai_api_key"
ENV DISCORD_TOKEN="your_discord_token"

# Run the bot
CMD [ "python", "main.py" ]
