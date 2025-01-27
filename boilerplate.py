from dotenv import load_dotenv
from pathlib import Path
import sys, os

def load_env_files():
    current_dir = Path(__file__).parent
    parent_dir = current_dir.parent
    
    parent_env = parent_dir / '.env'
    current_env = current_dir / '.env'
    
    files_loaded = False
    
    # Load parent .env first (sensitive keys)
    if parent_env.exists():
        load_dotenv(dotenv_path=parent_env)
        print(f"✓ Loaded parent .env from: {parent_env}")
        files_loaded = True
    else:
        print(f"⚠ Warning: No parent .env file found in {parent_env}")
        print("  This file should contain sensitive keys like API credentials")
    
    # Load current directory .env (project-specific settings)
    if current_env.exists():
        # override=True ensures repo-level vars overwrite parent vars if duplicated
        load_dotenv(dotenv_path=current_env, override=True)
        print(f"✓ Loaded repo .env from: {current_env}")
        files_loaded = True
    else:
        print(f"ℹ Note: No repo-level .env file found in {current_env}")
        print("  This file would contain project-specific non-sensitive settings")
    
    if not files_loaded:
        print("\n❌ Error: No .env files found in either location")
        sys.exit(1)
    
    print("\n✓ Environment variables loaded successfully")

if __name__ == "__main__":
    load_env_files()


    print("\nEnvironment Variables:")
    print("-" * 50)
    # Get all environment variables and sort them alphabetically
    env_vars = dict(sorted(os.environ.items()))
    
    # Print each variable, but mask sensitive ones
    for key, value in env_vars.items():
        # Mask values of keys that might be sensitive
        if any(sensitive in key.lower() for sensitive in ['key', 'secret', 'password', 'token']):
            masked_value = value[:4] + '*' * (len(value) - 4) if len(value) > 4 else '*' * len(value)
            print(f"{key}={masked_value}")
        else:
            print(f"{key}={value}")

import enum


import inspect
import logging
class Track:

    critical = 50
    error = 40
    warning = 30
    info = 20
    debug = 10

    def __init__(self,logger: logging.Logger):
        
        if not logger:
            print("!! Track object not initialised with valid logger object")
        self.logger = logger

    def __call__(self, logging_level: int,message: str = ''):
        """
        Level   Numeric value   What it means / When to use it
        logging.DEBUG       10  Detailed information, typically only of interest to a developer trying to diagnose a problem.
        logging.INFO        20  Confirmation that things are working as expected.
        logging.WARNING     30  An indication that something unexpected happened, or that a problem might occur in the near future (e.g. ‘disk space low’). The software is still working as expected.
        logging.ERROR       40  Due to a more serious problem, the software has not been able to perform some function.
        logging.CRITICAL    50  A serious error, indicating that the program itself may be unable to continue running."""

        caller = inspect.stack()[1]
        function_name = caller.function     

        track = f"<{function_name}>"
        if message != '':
            track += f": {message}"

        self.logger.log(logging_level, track)
        pass
