from together import Together
from dotenv import load_dotenv
import os
import re

# Načtení proměnných z .env souboru
load_dotenv()


def get_ai_response(
        user_message: str,
        model: str = "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free",
        delete_think: bool = True
) -> str:
    """
    Získá odpověď od AI na základě uživatelské zprávy.

    Args:
        user_message (str): Zpráva od uživatele
        model (str): Model AI, který se má použít
        delete_think (bool): Odstranit části odpovědi označené <think> (default: True)

    Returns:
        str: Odpověď od AI
    """
    try:
        # Získání API klíče
        api_key = os.getenv("TOGETHER_API_KEY")
        if not api_key:
            raise ValueError("TOGETHER_API_KEY nebyl nalezen v .env souboru")

        # Inicializace klienta
        client = Together(api_key=api_key)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )

        # Získání odpovědi
        ai_response = response.choices[0].message.content

        # Odstranění částí <think> pokud je delete_think True
        if delete_think:
            ai_response = re.sub(r'<think>.*?</think>', '', ai_response, flags=re.DOTALL)
            ai_response = ai_response.strip()

        return ai_response
    except Exception as e:
        return f"Chyba při komunikaci s AI: {str(e)}"


# Příklad použití
if __name__ == "__main__":
    user_input = "What are some fun things to do in New York?"

    ai_response = get_ai_response(user_input)
    print("Odpověď bez <think> částí:")
    print(ai_response)

    # ai_response_with_think = get_ai_response(user_input, delete_think=False)
    # print("\nOdpověď s <think> částmi:")
    # print(ai_response_with_think)