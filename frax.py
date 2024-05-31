import time
import json
import logging
import asyncio
from web3 import Web3
from web3.middleware import geth_poa_middleware
from telegram import Bot
from telegram.error import TelegramError
import os
from dotenv import load_dotenv
# Non-Functional
load_dotenv()  # take environment variables from .env.

# Configuration
INFURA_URL = os.getenv('FRAX_RPC')  # Replace with your Infura URL or another Ethereum node provider URL
CONTRACT_ADDRESS = "0x1578E6B0dA7048764ce14F7462567BEb911B11f2"
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')  # Replace with your Telegram bot token
CHAT_ID = -4250910125  # Replace with your Telegram chat ID
START_BLOCK = 4107893  # Block number to start monitoring from
POLL_INTERVAL = 10  # Polling interval in seconds
BLOCK_CHUNK_SIZE = 5000  # Number of blocks to query at a time

# Load ABI from api.json file
with open('api.json') as f:
    data = json.load(f)
    ABI = json.loads(data["result"])

# Initialize web3
web3 = Web3(Web3.HTTPProvider(INFURA_URL))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

# Initialize contract
contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_telegram_message(message):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
        logger.info(f"Sent message: {message}")
    except TelegramError as e:
        logger.error(f"Failed to send message: {e}")
    await asyncio.sleep(5)  # Add a 5-second delay after sending the message

def handle_event(event):
    # Parse event data
    token_address = event["args"]["token"]
    name = event["args"]["name"]
    symbol = event["args"]["symbol"]
    total_supply = event["args"]["totalSupply"]

    # Format message with a link to the contract address on basescan.com
    message = (f"New ETH Token Created:\n"
               f"Name: {name}\n"
               f"Symbol: {symbol}\n"
               f"Total Supply: {total_supply}\n"
               f"Address: [{token_address}](https://etherscan.io/address/{token_address})")

    # Schedule message sending via Telegram
    asyncio.create_task(send_telegram_message(message))

def get_event_logs(from_block, to_block):
    event_signature_hash = web3.keccak(text="TokenCreated(address,string,string,uint256)").hex()
    logs = web3.eth.get_logs({
        "fromBlock": from_block,
        "toBlock": to_block,
        "address": CONTRACT_ADDRESS,
        "topics": [event_signature_hash]
    })
    return logs

async def log_loop(poll_interval):
    latest_block = web3.eth.block_number
    current_block = START_BLOCK

    while True:
        try:
            new_block = web3.eth.block_number
            while current_block < new_block:
                end_block = min(current_block + BLOCK_CHUNK_SIZE, new_block)
                logger.info(f"Fetching logs from blocks {current_block} to {end_block}")
                logs = get_event_logs(current_block, end_block)
                logger.info(f"Fetched {len(logs)} logs")
                for log in logs:
                    event = contract.events.TokenCreated().process_log(log)
                    handle_event(event)
                current_block = end_block + 1

            await asyncio.sleep(poll_interval)
        except Exception as e:
            logger.error(f"Error fetching logs: {e}")
            await asyncio.sleep(poll_interval)

def main():
    asyncio.run(log_loop(POLL_INTERVAL))

if __name__ == "__main__":
    main()
