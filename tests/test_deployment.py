from app import app, build_room_url


def test_health_endpoint():
    response = app.test_client().get('/health')
    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_railway_room_link_uses_public_https_domain(monkeypatch):
    monkeypatch.setenv('RAILWAY_PUBLIC_DOMAIN', 'arena-test.up.railway.app')
    with app.test_request_context('/', base_url='http://localhost:8080'):
        assert build_room_url('ABCDE') == 'https://arena-test.up.railway.app/?room=ABCDE'


def test_custom_https_domain_is_preserved(monkeypatch):
    monkeypatch.delenv('RAILWAY_PUBLIC_DOMAIN', raising=False)
    with app.test_request_context('/', base_url='https://game.example.com'):
        assert build_room_url('ABCDE') == 'https://game.example.com/?room=ABCDE'


def test_local_room_link_keeps_lan_address(monkeypatch):
    monkeypatch.delenv('RAILWAY_PUBLIC_DOMAIN', raising=False)
    monkeypatch.setattr('app.get_lan_ip', lambda: '192.168.1.20')
    with app.test_request_context('/', base_url='http://localhost:5000'):
        assert build_room_url('ABCDE') == 'http://192.168.1.20:5000/?room=ABCDE'


def test_production_start_uses_railway_port_and_https(monkeypatch):
    import serve

    options = {}
    monkeypatch.setenv('PORT', '8080')
    monkeypatch.setenv('RAILWAY_ENVIRONMENT_ID', 'test-environment')
    monkeypatch.setattr(serve, 'serve', lambda application, **kwargs: options.update(kwargs))
    serve.main()
    assert options['host'] == '0.0.0.0'
    assert options['port'] == 8080
    assert options['url_scheme'] == 'https'
    assert options['threads'] == 8


def test_production_start_supports_local_http(monkeypatch):
    import serve

    options = {}
    monkeypatch.delenv('PORT', raising=False)
    monkeypatch.delenv('RAILWAY_ENVIRONMENT_ID', raising=False)
    monkeypatch.setattr(serve, 'serve', lambda application, **kwargs: options.update(kwargs))
    serve.main()
    assert options['port'] == 5000
    assert options['url_scheme'] == 'http'


def test_waitress_serves_game_health_and_room_links():
    import json
    from threading import Thread
    from urllib.request import Request, urlopen
    from waitress import create_server

    server = create_server(app, host='0.0.0.0', port=0, threads=8, url_scheme='https')
    Thread(target=server.run, daemon=True).start()
    base = 'http://127.0.0.1:' + str(server.effective_port)
    try:
        with urlopen(base + '/health', timeout=5) as response:
            assert json.load(response) == {'status': 'ok'}
        with urlopen(base + '/', timeout=5) as response:
            assert b'TIC TAC TOE' in response.read()
        request = Request(base + '/api/rooms', data=b'{}', headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=5) as response:
            assert json.load(response)['share_url'].startswith('https://')
    finally:
        server.close()
        server.task_dispatcher.shutdown()
