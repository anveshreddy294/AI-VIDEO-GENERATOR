import json
import re
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def generate_script_json(client, topic_name, output_file="video-output.json", provider='openai', model='gpt-4o', max_retries=3):
    """Generates the JSON file with script and animations using the LLM with automatic retries"""
    prompt = f"""Develop an educational script for this topic: {topic_name}

INSTRUCTIONS:
- Create an engaging and educational script about the topic
- Divide the script into logical scenes/fragments (between 6-8 scenes)
- For each scene, provide:
  1. The script text (narration) - BRIEF and CONCISE
  2. A detailed description of the Manim animation that should accompany that text
- Avoid using commercial logos (like ChatGPT, OpenAI, etc.)
- I DON'T want Python Manim code, just the description of what you want to visualize
- Animations should be specific and detailed so they can be implemented in Manim

LANGUAGE REQUIREMENT:
- The script and animations MUST be in the SAME LANGUAGE as the topic
- If the topic is in Spanish, write everything in Spanish
- If the topic is in English, write everything in English
- Match the language exactly

CRITICAL TIME RESTRICTION:
- The COMPLETE video must last MAXIMUM 60 seconds (1 minute)
- Each scene should last approximately 6-8 seconds
- The text of each scene must be SHORT (maximum 2-3 sentences)
- Animations must be SIMPLE and FAST

OUTPUT FORMAT (JSON):
Respond ONLY with a valid JSON array, where each element has this structure:
{{
  "text": "script text for this scene (BRIEF, 2-3 sentences maximum)",
  "animation": "detailed description of the specific animation for this fragment"
}}

Example of a scene:
{{
  "text": "Language models process text by converting it into numbers.",
  "animation": "Show the word 'Hello' in the center. Then, divide it into visual tokens with colored boxes. Finally, transform each token into a number (ID) with a morphing animation."
}}

IMPORTANT: Respond ONLY with the JSON array, without any additional text before or after."""

    
    # Retry loop for handling API failures
    for attempt in range(max_retries):
        try:
            print(f"Generating script for: {topic_name}... (Attempt {attempt + 1}/{max_retries})")
            
            if provider == 'openai':
                # OpenAI API call
                # Note: For reasoning models (o1, gpt-5-nano), we need extra tokens
                # because they use tokens for internal reasoning before producing output
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are an expert in creating educational video scripts. You always respond in valid JSON format without additional text. IMPORTANT: Match the language of the topic exactly - if the topic is in Spanish, write in Spanish; if in English, write in English."},
                        {"role": "user", "content": prompt}
                    ],
                    max_completion_tokens=16000  # Increased for reasoning models
                )
                
                # Debug: Print full response structure
                print(f"[DEBUG] Full response object: {response}")
                print(f"[DEBUG] Response choices: {response.choices}")
                
                if not response.choices:
                    print(f"[ERROR] No choices in response")
                    raise Exception("No choices in OpenAI response")
                
                content = response.choices[0].message.content
                if content is None:
                    print(f"[ERROR] message.content is None")
                    print(f"[DEBUG] Full message: {response.choices[0].message}")
                    print(f"[DEBUG] Finish reason: {response.choices[0].finish_reason}")
                    raise Exception(f"OpenAI returned None content. Finish reason: {response.choices[0].finish_reason}")
                
                response_text = content.strip()
                
            elif provider == 'claude':
                # Claude API call
                response = client.messages.create(
                    model=model,
                    max_tokens=4000,
                    system="You are an expert in creating educational video scripts. You always respond in valid JSON format without additional text. IMPORTANT: Match the language of the topic exactly - if the topic is in Spanish, write in Spanish; if in English, write in English.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                response_text = response.content[0].text.strip()
            
            else:
                raise ValueError(f"Unknown provider: {provider}")
            
            # Debug: Print the raw response
            print(f"[DEBUG] Raw API response length: {len(response_text)} characters")
            if len(response_text) == 0:
                print(f"[ERROR] Empty response from {provider} API")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"[RETRY] Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"[ERROR] Max retries reached. Giving up.")
                    return None
            
            # Show first 200 chars for debugging
            print(f"[DEBUG] Response preview: {response_text[:200]}...")
            
            # Try to extract JSON if wrapped in markdown
            if "```json" in response_text:
                response_text = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL).group(1)
            elif "```" in response_text:
                response_text = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL).group(1)
            
            # Parse JSON
            try:
                script_data = json.loads(response_text)
            except json.JSONDecodeError as json_err:
                print(f"[ERROR] Failed to parse JSON: {json_err}")
                print(f"[ERROR] Response text: {response_text[:500]}")
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"[RETRY] Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"[ERROR] Max retries reached. Giving up.")
                    return None
            
            # Save to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(script_data, f, ensure_ascii=False, indent=2)
            
            print(f"[OK] Script generated successfully: {output_file}")
            print(f"Total scenes: {len(script_data)}")
            
            return script_data
            
        except Exception as e:
            print(f"[ERROR] Error generating script: {e}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"[RETRY] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                print(f"[ERROR] Max retries reached. Giving up.")
                import traceback
                traceback.print_exc()
                return None
    
    # Should never reach here, but just in case
    return None

