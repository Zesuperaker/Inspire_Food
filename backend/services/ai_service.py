import json
import os
import base64
from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage


class AIService:
    """Service for handling AI operations with LangChain and Gemini Vision via OpenRouter"""

    def __init__(self):
        """Initialize LangChain with OpenRouter as provider for Gemini Vision"""
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set in environment variables")

        # Initialize ChatOpenAI with OpenRouter endpoint for vision
        self.llm = ChatOpenAI(
            model="google/gemini-2-flash-exp",  # Gemini 2 Flash with vision capabilities
            api_key=self.api_key,
            base_url="https://openrouter.io/api/v1",
            temperature=0.3,
            max_tokens=2000
        )

    def analyze_produce_from_image(self, image_data: str) -> Dict:
        """
        Analyze produce from image using Gemini Vision

        Args:
            image_data: Base64 encoded image data (data:image/jpeg;base64,...)

        Returns:
            Dict with keys: {
                'produce_name': str,
                'shelf_life_days': int,
                'is_expiring_soon': bool (>= 3 days),
                'is_expired': bool,
                'notes': str
            }
        """
        try:
            # Extract base64 data if it has data URI prefix
            if ',' in image_data:
                image_data = image_data.split(',')[1]

            # Create message with image
            message = HumanMessage(
                content=[
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": """You are an expert food scientist analyzing produce freshness from images.

Analyze the produce in this image and return a JSON response with EXACTLY this structure:
{
    "produce_name": "name of the produce identified",
    "shelf_life_days": estimated days until expiration (integer, minimum 0),
    "is_expiring_soon": true if 3 days or less remaining, false otherwise,
    "is_expired": true if 0 or fewer days, false otherwise,
    "notes": "brief assessment of freshness based on visual appearance"
}

Rules:
- shelf_life_days must be an integer between 0 and 30
- is_expiring_soon is true when shelf_life_days <= 3
- is_expired is true when shelf_life_days <= 0
- Analyze based on color, texture, visible damage, ripeness level
- Provide realistic estimates based on typical produce shelf lives
- Return ONLY valid JSON, no additional text"""
                    }
                ]
            )

            # Invoke the model
            response = self.llm.invoke([message])

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
            raise Exception(f"Error analyzing produce image: {str(e)}")

    def batch_analyze_produce_from_images(self, images: List[str]) -> Dict:
        """
        Analyze multiple produce items from images in batch

        Args:
            images: List of base64 encoded image data

        Returns:
            Dict with 'results' (list of analyses) and 'summary' (aggregate stats)
        """
        results = []
        expiring_soon_count = 0
        expired_count = 0

        for image_data in images:
            try:
                analysis = self.analyze_produce_from_image(image_data)
                results.append(analysis)

                if analysis.get('is_expiring_soon'):
                    expiring_soon_count += 1
                if analysis.get('is_expired'):
                    expired_count += 1

            except Exception as e:
                # Log error but continue processing
                results.append({
                    'produce_name': 'Unknown',
                    'shelf_life_days': 0,
                    'is_expiring_soon': True,
                    'is_expired': False,
                    'notes': f'Error analyzing image: {str(e)}'
                })
                expiring_soon_count += 1

        return {
            'results': results,
            'summary': {
                'total_scanned': len(images),
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