import json
import os

import pandas as pd
from dotenv import load_dotenv
from groq import Groq
import joblib

load_dotenv()


class CattleAIService:

    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))

        self.model = joblib.load(
            os.path.join(base_dir, "cattle_diseases_model.pkl")
        )

        self.model_features = joblib.load(
            os.path.join(base_dir, "model_features.pkl")
        )

        self.valid_symptoms = [
            f
            for f in self.model_features
            if f not in ["Age", "Temperature"] and not f.startswith("Animal")
        ]

        self.groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    def extract_symptoms_with_groq(self, farmer_text):
        system_prompt = f"""
            You are a veterinary assistant. Analyse the text and extract symptoms matching exactly this list:
            {self.valid_symptoms}
            Respond with a JSON object: {{"symptoms": ["symptom_name"]}}
        """
        try:
            completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f'Farmer text: "{farmer_text}"'},
                ],
                model="llama-3.1-8b-instant",
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            response_text = completion.choices[0].message.content.strip()
            result_json = json.loads(response_text)
            return result_json.get("symptoms", [])
        except Exception as e:
            print(f"Groq Extraction Error: {e}")
            return []

    def get_treatment_recommendation(self, disease, animal_type):
        system_prompt = """
            You are an expert livestock vet. Provide clear, concise, and professional treatment recommendation under 120 words using short bullet points. Include a vet disclaimer.
        """
        try:
            completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Treatment recommendation for a {animal_type} with {disease}",
                    },
                ],
                model="llama-3.1-8b-instant",
                temperature=0.3,
            )
            return completion.choices[0].message.content.strip()

        except Exception as e:
            print(f"Groq treatment Error: {e}")
            return "treatment temporarily unavailable"

    # Predict method
    def predict(self, animal_type, age, temp, description):
        # Use the LLM extraction utility to filter symptoms out of the incoming text string
        extracted_symptoms = self.extract_symptoms_with_groq(description)

        # Build baseline dictionary mapping all training features name to zero values
        input_data = {feature: 0 for feature in self.model_features}

        # Map raw numeric inputs to their respective matching feature keys
        input_data["Age"] = age
        input_data["Temperature"] = temp

        # Convert animal string into one-hot key format, e.g., 'Animal_cow'
        animal_key = f"Animal_{str(animal_type).strip().lower()}"
        if animal_key in input_data:
            input_data[animal_key] = 1

        for symptom in extracted_symptoms:
            if symptom in input_data:
                input_data[symptom] = 1

        # Build a single-row DataFrame with columns in the exact order/names the
        # model was trained on. This is what the model actually expects (it was
        # fit on a DataFrame, not a raw array) and removes the
        # "X does not have valid feature names" warning entirely.
        input_df = pd.DataFrame([input_data], columns=self.model_features)

        # Predict using our model, passing the named DataFrame instead of a bare list
        prediction = self.model.predict(input_df)

        # Extract the prediction at index 0
        predicted_disease = prediction[0]

        treatment_plan = self.get_treatment_recommendation(
            predicted_disease, animal_type
        )

        # Return consolidated final pipeline payload output directly back to DRF response
        return {
            "status": "success",
            "extracted_symptoms_by_ai": extracted_symptoms,
            "predicted_disease": predicted_disease,
            "treatment_recommendation": treatment_plan,
        }