import os
import discord
import requests
import logging
import re
import asyncio
import json
import time
from keep_alive import keep_alive

# Set up logging configuration
logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
client = discord.Client(intents=intents)

# File to store scheduled repositories
SCHEDULED_REPOSITORIES_FILE = "scheduled_repositories.json"


def get_latest_commit(repository):
    # Make a request to the GitHub API to get the latest commit information for the specified repository
    try:
        response = requests.get(
            f'https://api.github.com/repos/{repository}/commits')
        response.raise_for_status()
        data = response.json()

        # Get the commit message, author, and hash from the latest commit
        commit_message = data[0]['commit']['message']
        commit_author = data[0]['commit']['author']['name']
        commit_hash = data[0]['sha']

        # Return the commit message, author, and hash
        return commit_message, commit_author, commit_hash
    except requests.exceptions.RequestException as e:
        # Handle the error
        logging.error(f'Request failed: {e}')
        return None
    except (KeyError, IndexError) as e:
        # Handle the error
        logging.error(f'Failed to retrieve commit information: {e}')
        return None


async def send_commit_info(repository, channel):
    # Get the latest commit information for the specified repository
    commit_info = get_latest_commit(repository)
    if commit_info is not None:
        commit_message, commit_author, commit_hash = commit_info
        # Check if the commit hash is different from the last recorded commit hash for the repository
        if last_commit_hashes.get(repository) != commit_hash:
            # Send the commit message and author to the specified channel with success.gif
            await channel.send(
                f'The latest commit for {repository} was made by {commit_author}, '
                f'with the message: {commit_message}',
                file=discord.File('success.gif'))
            logging.info(
                f'Sent commit information for {repository} to channel {channel.name}')
            # Update the last recorded commit hash for the repository
            last_commit_hashes[repository] = commit_hash
    else:
        # Send an error message to the channel
        await channel.send(
            f'Failed to retrieve commit information for {repository}. Please check the repository name and try again.'
        )


RATE_LIMIT_DELAY = 10  # Delay in seconds between checking each repository


async def check_commit_updates():
    await client.wait_until_ready()
    while not client.is_closed():
        # Check for updates in all scheduled repositories
        for repository, channel_ids in scheduled_repositories.items():
            if isinstance(channel_ids, int):
                channel_ids = [channel_ids]  # Convert single channel ID to a list

            for channel_id in channel_ids:
                channel = client.get_channel(channel_id)
                await send_commit_info(repository, channel)
                await asyncio.sleep(RATE_LIMIT_DELAY)  # Use asyncio.sleep instead of time.sleep

        # Save the scheduled repositories to file
        await save_scheduled_repositories()

        # Sleep for 1 minute before checking for updates again
        await asyncio.sleep(60)


async def save_scheduled_repositories():
    try:
        with open(SCHEDULED_REPOSITORIES_FILE, 'w') as file:
            json.dump(scheduled_repositories, file)
    except IOError:
        logging.error('Failed to save scheduled repositories')


@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    logging.info(f'Logged in as {client.user}')
    client.loop.create_task(check_commit_updates())

    # Load scheduled repositories from file (if available)
    load_scheduled_repositories()


@client.event
@client.event
@client.event
async def on_message(message):
    # Ignore messages sent by the bot itself
    if message.author == client.user:
        return

    # Check if the message content starts with the command prefix or bot mention
    if message.content.startswith('!latest_commit') or client.user.mentioned_in(message):
        # Check if the message was sent in a guild
        if isinstance(message.channel, discord.TextChannel):
            # Parse the command arguments
            args = message.content.split()[1:]
            if len(args) != 2:
                await message.channel.send(
                    'Invalid number of arguments. Usage: !latest_commit <repository> <channel>'
                )
                return
            repository, channel_name = args

            # Validate the repository name
            repository_regex = r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$'

            if not re.match(repository_regex, repository):
                api_address = f'https://github.com/{repository}'
                await message.channel.send(
                    f'Invalid repository name: {repository}. '
                    f'Please check the repository name or access it directly at: {api_address}'
                )
                return

            # Get the channel to send the commit information to
            channel = discord.utils.get(message.guild.channels, name=channel_name)
            if channel is None:
                await message.channel.send(f'Channel {channel_name} not found')
                return

            # Check if the repository is already being tracked
            if repository in scheduled_repositories:
                channel_ids = scheduled_repositories[repository]
                if isinstance(channel_ids, int):
                    channel_ids = [channel_ids]
            else:
                # Create a new entry for the repository and initialize the list of tracked channels
                channel_ids = []

            if channel.id in channel_ids:
                await message.channel.send(
                    f'The repository {repository} is already being tracked in {channel_name}'
                )
                return

            # Add the channel ID to the list of tracked channels for the repository
            channel_ids.append(channel.id)
            scheduled_repositories[repository] = channel_ids

            # Save the scheduled repositories to file
            await save_scheduled_repositories()

            # Send a confirmation message to the user
            await message.channel.send(
                f'Successfully scheduled commit information for {repository} '
                f'to be sent to {channel_name} when there are new commits')




def load_scheduled_repositories():
    global scheduled_repositories
    if os.path.isfile(SCHEDULED_REPOSITORIES_FILE):
        try:
            with open(SCHEDULED_REPOSITORIES_FILE, 'r') as file:
                scheduled_repositories = json.load(file)
                last_commit_hashes.update({
                    repo: None
                    for repo in scheduled_repositories
                })  # Initialize last commit hashes
        except IOError:
            logging.error('Failed to load scheduled repositories')


# Store the last commit hash for each repository
last_commit_hashes = {}

# Load scheduled repositories from file (if available)
scheduled_repositories = {}
load_scheduled_repositories()

# Keep the bot alive
keep_alive()

# Use an environment variable to store the Discord token
my_secret = os.environ['DISCORD_TOKEN']
client.run(my_secret)
