import base64
import io
from PIL import Image, ImageDraw, ImageFont
from vigilador_tecnologico.integrations.gemini import GeminiAdapter
from vigilador_tecnologico.integrations.model_profiles import GEMINI_ROBOTICS_ER_16_MODEL

def create_text_image():
    img = Image.new('RGB', (800, 400), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    # Use default font if nothing else
    text = "Technology Report: Quantum Computing\nAuthor: Dr. Smith\nDate: 2024-05-10\n\nSummary: Quantum computing is advancing rapidly."
    d.text((10,10), text, fill=(0,0,0))
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

def main():
    adapter = GeminiAdapter(model=GEMINI_ROBOTICS_ER_16_MODEL)
    img_bytes = create_text_image()
    
    try:
        response = adapter.generate_content_parts(
            parts=[
                {"text": "Parse this document image. Return JSON with raw_text and page_count."},
                {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(img_bytes).decode("ascii")}}
            ],
            system_instruction="Extract document text and return only JSON.",
            generation_config={
                "temperature": 0.0,
                "responseMimeType": "application/json",
            }
        )
        print("Response:", response)
    except Exception as e:
        print("Error:", repr(e))

if __name__ == "__main__":
    main()
