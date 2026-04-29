import base64
from vigilador_tecnologico.integrations.gemini import GeminiAdapter
from vigilador_tecnologico.integrations.model_profiles import GEMINI_ROBOTICS_ER_16_MODEL
from vigilador_tecnologico.integrations.document_ingestion import _parse_model_json_response

def main():
    adapter = GeminiAdapter(model=GEMINI_ROBOTICS_ER_16_MODEL)
    # Tiny 1x1 white PNG
    tiny_png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=")
    try:
        response = adapter.generate_content_parts(
            parts=[
                {"text": "Parse this image document for a technology surveillance pipeline. Return JSON with raw_text and page_count."},
                {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(tiny_png).decode("ascii")}}
            ],
            system_instruction="Extract document text and return only JSON.",
            generation_config={
                "temperature": 0.0,
                "responseMimeType": "application/json",
            }
        )
        print("Raw response:", response)
        payload = _parse_model_json_response(response)
        print("Parsed payload:", payload)
    except Exception as e:
        print("Error:", repr(e))

if __name__ == "__main__":
    main()
