import logging
import os
from datetime import datetime

# Generate log file name based on current timestamp
LOG_FILE = f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.log"

# Define the directory path for logs
logs_dir = os.path.join(os.getcwd(), "logs")

# Create the directory if it doesn't exist
os.makedirs(logs_dir, exist_ok=True)

# Full path to the actual log file
LOG_FILE_PATH = os.path.join(logs_dir, LOG_FILE)

# Configure the logging format and level
logging.basicConfig(
    filename=LOG_FILE_PATH,
    format="[ %(asctime)s ] %(lineno)d %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

if __name__ == '__main__':
    logging.info("Logging has started.")