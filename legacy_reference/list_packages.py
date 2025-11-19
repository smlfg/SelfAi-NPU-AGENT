import os
import qai_hub_models

try:
    models_path = os.path.join(os.path.dirname(qai_hub_models.__file__), "models", "phi_3_5_mini_instruct")
    print(f"Listing contents of: {models_path}")
    for item in os.listdir(models_path):
        print(item)
except FileNotFoundError:
    print(f"Directory not found: {models_path}")
except Exception as e:
    print(f"An error occurred: {e}")