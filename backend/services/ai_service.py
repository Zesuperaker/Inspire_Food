"""
AIService: Vision AI analysis for produce freshness detection

Uses LangChain + OpenRouter to access Google Gemini 2 Flash vision model.
Analyzes produce images to extract:
- Produce name/type
- Estimated shelf life in days
- Freshness status (fresh, expiring soon, expired)
- Storage recommendations

Architecture:
- LangChain abstracts the LLM interface (easy to swap providers)
- OpenRouter endpoint (https://openrouter.ai) provides API access to Gemini
- HumanMessage with image_url supports vision analysis
- Structured JSON responses enable reliable data extraction
"""

import json
import os
import base64
from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage


class AIService:
    """
    Service for AI-powered produce analysis using vision models.

    Provides:
    - Single image analysis: analyze one produce item
    - Batch analysis: analyze multiple items efficiently
    - Storage recommendations: AI-generated storage tips

    Uses LangChain with OpenRouter as the provider for cost-effective
    access to frontier vision models (Gemini 2 Flash).
    """

    def __init__(self):
        """
        Initialize LLM client with OpenRouter configuration.

        Expects OPENROUTER_API_KEY env variable to be set.
        Uses Gemini 2 Flash for fast, cost-effective vision analysis.

        Raises:
            ValueError: If OPENROUTER_API_KEY not found in environment
        """
        # Load API key from environment
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set in environment variables")

        # Initialize LangChain ChatOpenAI client
        # Note: Despite the name, ChatOpenAI supports any OpenAI-compatible endpoint
        self.llm = ChatOpenAI(
            model="google/gemini-3-flash-preview",  # Gemini 2 Flash via OpenRouter
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",  # OpenRouter API endpoint
            temperature=0.3,  # Lower temp = more deterministic/consistent responses
            max_tokens=2000  # Sufficient for JSON response + reasoning
        )

    def analyze_produce_from_image(self, image_data: str) -> Dict:
        """
        Analyze a single produce item from a base64 encoded image.

        Vision Analysis Process:
        1. Parse base64 image data (handle data URI prefix)
        2. Create HumanMessage with image_url for vision processing
        3. Prompt AI to analyze produce freshness visually
        4. Extract structured JSON response
        5. Validate all required fields present
        6. Ensure numeric values in valid ranges

        Freshness Rules:
        - is_expiring_soon: true if shelf_life_days <= 3
        - is_expired: true if shelf_life_days <= 0
        - shelf_life_days: clamped to [0, 30] range

        Args:
            image_data: Base64 encoded image string
                       Can have data URI prefix (data:image/jpeg;base64,XXX)
                       or just raw base64 (XXX)

        Returns:
            Dict with structure:
            {
                'produce_name': str (e.g., 'Apple', 'Banana'),
                'shelf_life_days': int (0-30),
                'is_expiring_soon': bool,
                'is_expired': bool,
                'notes': str (freshness assessment)
            }

        Raises:
            Exception: If image analysis fails or JSON parsing fails

        Example:
            image_b64 = '/9j/4AAQSkZJRgABA...'  # JPEG base64
            result = ai_service.analyze_produce_from_image(image_b64)
            # Returns: {
            #   'produce_name': 'Apple',
            #   'shelf_life_days': 7,
            #   'is_expiring_soon': False,
            #   'is_expired': False,
            #   'notes': 'Red apple, firm texture, no visible damage'
            # }
        """
        try:
            # Step 1: Clean image data - handle data URI prefix
            # Input can be: "data:image/jpeg;base64,/9j/4AAQ..."
            # or just: "/9j/4AAQ..."
            if ',' in image_data:
                # Remove data URI prefix (everything before comma)
                image_data = image_data.split(',')[1]

            # Step 2: Create vision message with image
            # HumanMessage supports multimodal content (text + images)
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
                        # Detailed system prompt for consistent produce analysis
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

            # Step 3: Invoke LLM with image and prompt
            # LangChain handles API call, token counting, etc.
            response = self.llm.invoke([message])

            # Step 4: Extract content from response object
            # Response is an AIMessage object, extract .content attribute
            if hasattr(response, 'content'):
                content = response.content
            else:
                content = str(response)

            # Step 5: Validate response is not empty/invalid
            if not content or not isinstance(content, str):
                raise ValueError(f"Invalid response from AI model: {response}")

            # Step 6: Clean whitespace
            content = content.strip()
            if not content:
                raise ValueError("AI model returned empty response")

            # Step 7: Strip markdown code blocks if LLM wrapped JSON in ```json ... ```
            # Some models do this even when told not to
            if content.startswith("```"):
                # Remove opening markdown fence
                content = content.split("```", 2)[1]
                # Remove language specifier (json)
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            if content.endswith("```"):
                # Remove closing fence
                content = content[:-3].strip()

            # Step 8: Parse JSON response
            # With error handling to show what we got if parsing fails
            try:
                produce_data = json.loads(content)
            except json.JSONDecodeError as e:
                # Include first 500 chars of invalid response for debugging
                raise ValueError(f"AI response is not valid JSON. Response: {content[:500]}") from e

            # Step 9: Validate required fields present
            # Ensures response has exactly the fields we expect
            required_fields = ['produce_name', 'shelf_life_days', 'is_expiring_soon', 'is_expired', 'notes']
            if not all(field in produce_data for field in required_fields):
                raise ValueError(f"Missing required fields in response. Got: {produce_data.keys()}")

            # Step 10: Clamp shelf_life_days to valid range [0, 30]
            # Handles cases where AI estimates outside reasonable bounds
            produce_data['shelf_life_days'] = max(0, min(30, int(produce_data['shelf_life_days'])))

            # Step 11: Return validated, cleaned response
            return produce_data

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse AI response as JSON: {str(e)}")
        except Exception as e:
            raise Exception(f"Error analyzing produce image: {str(e)}")

    def batch_analyze_produce_from_images(self, images: List[str]) -> Dict:
        """
        Analyze multiple produce images in a batch.

        Processes each image sequentially (not parallelized, but could be optimized).
        Aggregates freshness statistics for efficient session updates.

        Error Handling:
        - If an image fails to analyze, inserts placeholder result
        - Continues processing remaining images
        - Includes error message in notes field

        Args:
            images: List of base64 encoded image strings

        Returns:
            Dict with structure:
            {
                'results': [list of produce_data dicts (same as single analysis)],
                'summary': {
                    'total_scanned': int,
                    'expiring_soon_count': int,
                    'expired_count': int
                }
            }

        Example:
            results = ai_service.batch_analyze_produce_from_images([
                img1_base64,
                img2_base64,
                img3_base64
            ])
            # Processes all 3 images, returns aggregated results
        """
        results = []
        expiring_soon_count = 0
        expired_count = 0

        # Process each image
        for image_data in images:
            try:
                # Analyze individual image
                analysis = self.analyze_produce_from_image(image_data)
                results.append(analysis)

                # Tally expiring soon items
                if analysis.get('is_expiring_soon'):
                    expiring_soon_count += 1

                # Tally expired items
                if analysis.get('is_expired'):
                    expired_count += 1

            except Exception as e:
                # If analysis fails, add error placeholder
                # This allows batch to continue even if one image fails
                results.append({
                    'produce_name': 'Unknown',
                    'shelf_life_days': 0,
                    'is_expiring_soon': True,  # Treat as expiring for safety
                    'is_expired': False,
                    'notes': f'Error analyzing image: {str(e)}'
                })
                expiring_soon_count += 1  # Count failed images as "expiring soon"

        # Return results + computed summary statistics
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
        Generate AI-powered storage recommendations for a produce type.

        Uses LangChain PromptTemplate to structure the prompt,
        then invokes LLM with pipe operator (|).

        Output: 2-3 sentence recommendations focusing on:
        - Optimal temperature (room temp vs refrigerated)
        - Humidity requirements
        - Container/bag type
        - Special handling notes

        Args:
            produce_name: Type of produce (e.g., 'Apple', 'Spinach', 'Banana')

        Returns:
            str: Storage recommendations (2-3 sentences)

        Example:
            tips = ai_service.get_storage_recommendations('Banana')
            # Returns: "Store bananas at room temperature away from direct
            #           sunlight in a ventilated area. Avoid placing near
            #           ethylene producers like apples..."

        Raises:
            Returns error message as string if API fails
        """
        # Define prompt template with variable for produce name
        prompt_template = PromptTemplate(
            input_variables=["produce_name"],
            template="""As a food storage expert, provide brief storage recommendations for {produce_name}.
            Keep response to 2-3 sentences maximum.
            Focus on: optimal temperature, humidity, container type, and any special handling."""
        )

        try:
            # Create chain using LangChain pipe operator
            # Syntax: prompt | llm (applies prompt then passes to LLM)
            chain = prompt_template | self.llm

            # Invoke chain with produce name
            response = chain.invoke({"produce_name": produce_name})

            # Extract text from response object
            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)

        except Exception as e:
            # Return error message as fallback
            # Better than raising since this is a non-critical feature
            return f"Could not retrieve storage recommendations: {str(e)}"