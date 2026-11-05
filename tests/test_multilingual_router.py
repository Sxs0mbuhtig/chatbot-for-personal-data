from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_multilingual_translation_endpoint():
    response = client.get("/api/v1/translate", params={"term": "computer", "target": "km"})
    assert response.status_code == 200
    data = response.json()
    assert data["term"] == "computer"
    assert data["translation"] == "កុមព្យូទ័រ"

def test_multilingual_batch_lookup():
    response = client.post("/api/v1/multilingual", json={"term": "security"})
    assert response.status_code == 200
    data = response.json()
    assert data["anchor_term"] == "security"
    assert data["translations"]["en"] == "security"
    assert data["translations"]["km"] == "សុវត្ថិភាព"
