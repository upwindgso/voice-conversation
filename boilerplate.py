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

