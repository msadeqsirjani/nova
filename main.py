from src.config import Config
from src.assistant import Assistant

def main():
    try:
        # Initialize configuration
        config = Config()
        
        # Create and start assistant
        assistant = Assistant(config)
        
        print("Starting virtual assistant...")
        assistant.start()
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {str(e)}")
        
if __name__ == "__main__":
    main()