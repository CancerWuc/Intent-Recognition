import json

from flask import jsonify


def build_payload(code=200, msg='success', data=None):
    return {
        'code': code,
        'msg': msg,
        'data': data,
    }


def api_response(code=200, msg='success', data=None, http_status=None, **extra):
    payload = build_payload(code=code, msg=msg, data=data)
    if http_status is None:
        http_status = 200 if 200 <= code < 300 else code
    return jsonify(payload), http_status


def api_success(data=None, msg='success', code=200, http_status=None, **extra):
    return api_response(code=code, msg=msg, data=data, http_status=http_status, **extra)


def api_error(msg='failed', code=400, data=None, http_status=None, **extra):
    return api_response(code=code, msg=msg, data=data, http_status=http_status, **extra)


def sse_event(code=200, msg='success', data=None, **extra):
    payload = build_payload(code=code, msg=msg, data=data)
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def sse_content(content, msg='success', code=200, **extra):
    return sse_event(code=code, msg=msg, data={'content': content})


def sse_meta(meta, msg='success', code=200, **extra):
    return sse_event(code=code, msg=msg, data={'meta': meta})


def sse_error(msg='failed', code=400, **extra):
    return sse_event(code=code, msg=msg, data=None)


def sse_done():
    return "data: [DONE]\n\n"
