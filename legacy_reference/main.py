from selfai.core.agent import Agent

def main():
    """Main function to run the interactive agent chat."""
    print("Initializing SelfAI Agent...")
    try:
        agent = Agent(provider_name="local-ollama")
        print("Agent initialized. You can start chatting.")
        print("Type 'exit' or 'quit' to end the session.")
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
        print("Please ensure that your config_extended.yaml is set up correctly and the Ollama server is running.")
        return

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in {"exit", "quit"}:
                print("Goodbye!")
                break
            
            if not user_input:
                continue

            agent_response = agent.run(user_input)
            print(f"Agent: {agent_response}")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()

