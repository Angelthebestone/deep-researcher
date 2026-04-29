from vigilador_tecnologico.integrations.gemini import GeminiAdapter
from vigilador_tecnologico.integrations.model_profiles import GEMINI_ROBOTICS_ER_16_MODEL
from vigilador_tecnologico.integrations.document_ingestion import _parse_model_json_response

def main():
    adapter = GeminiAdapter(model=GEMINI_ROBOTICS_ER_16_MODEL)
    try:
        response = adapter.generate_content_parts(
            parts=[{"text": "Parse this text document for a technology surveillance pipeline. Return JSON with raw_text and page_count. Preserve tables as tab-separated text. Do not summarize and do not add commentary."}, {"text": "Document content: Hello World, this is page 1. Page 2 has some tech."}],
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
