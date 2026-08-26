from app import app


def test_trophies_api_post_and_get():
    client = app.test_client()
    # increment a test league trophy
    resp = client.post('/trophies', json={'league':'unittest','winner':'X'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('status') == 'ok'
    # fetch trophies
    resp2 = client.get('/trophies')
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert 'trophies' in data2
    assert 'unittest' in data2['trophies']
    assert data2['trophies']['unittest']['X'] >= 1
