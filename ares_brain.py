from langchain_ollama import OllamaLLM

# Initialize the NEW Brain (Llama 3.2)
# This model is much better at following "Safety Rules"
llm = OllamaLLM(model="llama3.2")


def get_commander_orders(game_summary):
    """
    Sends the game state to the Local LLM.
    """
    # STRATEGIC LOGIC PROMPT
    prompt = f"""
    You are a StarCraft II Bot. Analyze the enemy and choose a strategy.

    LOGIC GATES:
    1. IF enemy has (Tanks, Bunkers, Planetary Fortress) -> STOP RUSH. Output: MACRO.
    2. IF enemy has (Void Rays, Banshees, Battlecruisers) -> STOP RUSH. Output: COUNTER.
    3. IF enemy has NO army and NO defense -> ATTACK. Output: RUSH.
    4. IF I have 0 Gas -> MACRO.

    Situation: "{game_summary}"

    COMMAND (Reply with ONE word: RUSH, MACRO, or COUNTER):
    """

    response = llm.invoke(prompt)

    # Cleaning the output (Llama sometimes puts the word in **bold**)
    cleaned_order = response.replace("*", "").replace(".", "").strip().upper()

    # Grab just the first word
    first_word = cleaned_order.split()[0]

    # Safety Check
    if first_word not in ["RUSH", "MACRO", "COUNTER"]:
        return "MACRO"  # Play safe if confused

    return first_word


# Test the Llama Brain
if __name__ == "__main__":
    print("Initializing Strategic Engine (Llama 3.2)...")

    # Test 1: Easy Win
    test_1 = "Enemy has no army. I have 20 Zerglings."
    print(f"\nSituation: {test_1}")
    print(f"Order: {get_commander_orders(test_1)}")

    # Test 2: The Tank Test (The Hard One)
    test_2 = "Enemy is turtling with Siege Tanks and Walls. I cannot break them."
    print(f"\nSituation: {test_2}")
    print(f"Order: {get_commander_orders(test_2)}")
