import json

import gemini_movie_research as research


class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return json.dumps(self.payload).encode('utf-8')


def test_retired_gemini_25_model_setting_is_migrated_to_38_flash(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    monkeypatch.setenv('GEMINI_RESEARCH_MODEL', 'gemini-2.5-flash')
    payload = {'candidates': [{'content': {'parts': [{'text': json.dumps({'title':'Parasite','media_type':'feature film','release_year':'2019','production_countries':['South Korea'],'original_language':'Korean','directors':['Bong Joon-ho'],'genres':['Thriller'],'overview':'A poor family schemes to become employed by a wealthy family.','identity_match':True,'uncertainty':''})}]}, 'groundingMetadata': {'groundingChunks': [{'web': {'title':'Official Film Page','uri':'https://www.neonrated.com/film/parasite'}},{'web': {'title':'Festival Catalogue','uri':'https://www.festival-cannes.com/en/f/parasite/'}}]}}]}
    captured = {}
    def fake_urlopen(request, **kwargs):
        captured['url'] = request.full_url
        captured['api_key_header'] = request.get_header('X-goog-api-key')
        return FakeResponse(payload)
    monkeypatch.setattr(research, 'urlopen', fake_urlopen)
    result = research.fetch_gemini_movie_metadata('Parasite')
    assert '/gemini-3.8-flash:generateContent' in captured['url']
    assert 'key=' not in captured['url']
    assert captured['api_key_header'] == 'test-key'
    assert result['found'] is True
    assert 'အလိုအလျောက်ပြောင်း' in result['status']
