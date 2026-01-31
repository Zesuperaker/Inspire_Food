import json
import os
from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate


class AIService:
    """Service for handling AI operations with LangChain and Gemini via OpenRouter"""

    def __init__(self):
        """Initialize LangChain with OpenRouter as provider for Gemini"""
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set in environment variables")

        # Initialize ChatOpenAI with OpenRouter endpoint
        # Using Gemini through OpenRouter
        self.llm = ChatOpenAI(
            model="google/gemini-3-flash-preview",  # Gemini model via OpenRouter
            api_key=self.api_key,
            base_url="https://openrouter.io/api/v1",
            temperature=0.3,  # Low temperature for consistent JSON output
            max_tokens=2000
        )

    def analyze_produce(self, produce_description: str) -> Dict:
        """
        Analyze produce using Gemini to determine shelf life

        Args:
            produce_description: Description of the produce (name, appearance, etc.)

        Returns:
            Dict with keys: {
                'produce_name': str,
                'shelf_life_days': int,
                'is_expiring_soon': bool (>= 3 days),
                'is_expired': bool,
                'notes': str
            }
        """

        prompt_template = PromptTemplate(
            input_variables=["produce_description"],
            template="""You are an expert food scientist analyzing produce freshness.

            Given this description of produce: {produce_description}

            Analyze the produce and return a JSON response with EXACTLY this structure:
            {{
                "produce_name": "name of the produce",
                "shelf_life_days": estimated days until expiration (integer, minimum 0),
                "is_expiring_soon": true if 3 days or less remaining, false otherwise,
                "is_expired": true if 0 or fewer days, false otherwise,
                "notes": "brief assessment of freshness"
            }}

            Rules:
            - shelf_life_days must be an integer between 0 and 30
            - is_expiring_soon is true when shelf_life_days <= 3
            - is_expired is true when shelf_life_days <= 0
            - Provide realistic estimates based on typical produce shelf lives
            - Return ONLY valid JSON, no additional text
            """
        )

        try:
            # Create the chain
            chain = prompt_template | self.llm

            # Invoke the chain
            response = chain.invoke({"produce_description": produce_description})

            # Extract content from the response
            if hasattr(response, 'content'):
                content = response.content
            else:
                content = str(response)

            # Parse the JSON response
            produce_data = json.loads(content)

            # Validate required fields
            required_fields = ['produce_name', 'shelf_life_days', 'is_expiring_soon', 'is_expired', 'notes']
            if not all(field in produce_data for field in required_fields):
                raise ValueError(f"Missing required fields in response. Got: {produce_data.keys()}")

            # Ensure shelf_life_days is within valid range
            produce_data['shelf_life_days'] = max(0, min(30, int(produce_data['shelf_life_days'])))

            return produce_data

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse AI response as JSON: {str(e)}")
        except Exception as e:
            raise Exception(f"Error analyzing produce: {str(e)}")

    def batch_analyze_produce(self, produce_list: List[str]) -> Dict:
        """
        Analyze multiple produce items in batch

        Args:
            produce_list: List of produce descriptions

        Returns:
            Dict with 'results' (list of analyses) and 'summary' (aggregate stats)
        """
        results = []
        expiring_soon_count = 0
        expired_count = 0

        for produce_desc in produce_list:
            try:
                analysis = self.analyze_produce(produce_desc)
                results.append(analysis)

                if analysis.get('is_expiring_soon'):
                    expiring_soon_count += 1
                if analysis.get('is_expired'):
                    expired_count += 1

            except Exception as e:
                # Log error but continue processing
                results.append({
                    'produce_name': produce_desc,
                    'shelf_life_days': 0,
                    'is_expiring_soon': True,
                    'is_expired': False,
                    'notes': f'Error analyzing: {str(e)}'
                })
                expiring_soon_count += 1

        return {
            'results': results,
            'summary': {
                'total_scanned': len(produce_list),
                'expiring_soon_count': expiring_soon_count,
                'expired_count': expired_count
            }
        }

    def get_storage_recommendations(self, produce_name: str) -> str:
        """
        Get storage recommendations for a specific produce type

        Args:
            produce_name: Name of the produce

        Returns:
            String with storage recommendations
        """
        prompt_template = PromptTemplate(
            input_variables=["produce_name"],
            template="""As a food storage expert, provide brief storage recommendations for {produce_name}.
            Keep response to 2-3 sentences maximum.
            Focus on: optimal temperature, humidity, container type, and any special handling."""
        )

        try:
            chain = prompt_template | self.llm
            response = chain.invoke({"produce_name": produce_name})

            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)

        except Exception as e:
            return f"Could not retrieve storage recommendations: {str(e)}"