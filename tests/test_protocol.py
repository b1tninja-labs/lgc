"""The RFC 8522 JSend response decoder (RFC 8522 sec. 2.3, Appendix A).

The bodies are the RFC's own examples, with one correction the RFC needs: its sec. 2.3.1 example
is not valid JSON (no comma after the ``router`` member), which `test_rfc8522_section_2_3_1_example_is_not_valid_json`
pins. The corrected text is what the fixtures below use.
"""

from __future__ import annotations

import datetime
import json

import pytest

from lgc import protocol
from lgc.protocol import Error, Fail, ResponseError, Success, decode_response

# RFC 8522 sec. 2.3.1 para 10 as printed (comma missing after "router").
SECTION_2_3_1_PRINTED = b"""{
     "status" : "success",
     "data" : {
       "router" : "route-server.lookingglass.example.net"
       "performed_at" : "2014-10-15T17:15:34Z",
       "runtime" : 2.63,
       "output" : [
         "full raw output from the observing router..."
       ],
       "format" : "text/plain"
     }
   }"""
SECTION_2_3_1 = SECTION_2_3_1_PRINTED.replace(b'example.net"\n', b'example.net",\n')

SECTION_2_3_2 = b"""{
     "status" : "fail",
     "data" : {
       "performed_at" : "2014-10-18T20:04:37Z",
       "runtime" : 10.37,
       "output" : [
         "Sending 5, 100-byte ICMP Echos to 192.0.2.5",
         ".....",
         "Success rate is 0 percent (0/5)"
       ],
       "format" : "text/plain",
       "router" : "route-server.lookingglass.example.net"
     }
   }"""

SECTION_2_3_3 = b"""{
     "status" : "error",
     "message" : "Unrecognized host or address."
   }"""

# Sec. 3.3.2 para 16: no performed_at and no runtime, although sec. 2.3.1 says they must be present.
SECTION_3_3_2 = b"""{
     "status" : "success",
     "data" : {
       "id" : 1,
       "name" : "customer-edge.lookingglass.example.net",
       "format" : "text/plain,text/x.netconf",
       "country" : "de",
       "autonomous_system" : 64512
     }
   }"""


def test_rfc8522_section_2_3_1_example_is_not_valid_json():
    with pytest.raises(json.JSONDecodeError):
        json.loads(SECTION_2_3_1_PRINTED)
    with pytest.raises(ResponseError, match="not valid JSON"):
        decode_response(200, SECTION_2_3_1_PRINTED)


def test_jsend_variants():
    success = decode_response(200, SECTION_2_3_1)
    assert isinstance(success, Success)
    assert success.router == "route-server.lookingglass.example.net"
    assert success.performed_at == datetime.datetime(2014, 10, 15, 17, 15, 34, tzinfo=datetime.UTC)
    assert success.runtime == 2.63
    assert success.format == "text/plain"
    assert success.lines() == ("full raw output from the observing router...",)
    assert success.http_consistent

    fail = decode_response(200, SECTION_2_3_2)
    assert isinstance(fail, Fail)
    assert fail.lines()[-1] == "Success rate is 0 percent (0/5)"
    assert fail.runtime == 10.37

    error = decode_response(400, SECTION_2_3_3)
    assert isinstance(error, Error)
    assert error.message == "Unrecognized host or address."
    assert error.code is None
    assert error.data is None
    assert error.http_consistent


def test_router_details_reply_has_no_timing_members():
    with pytest.raises(ResponseError, match="performed_at or runtime"):
        decode_response(200, SECTION_3_3_2)
    details = decode_response(200, SECTION_3_3_2, function="router details")
    assert isinstance(details, Success)
    assert details.data["id"] == 1
    assert details.data["autonomous_system"] == 64512
    assert details.performed_at is None
    assert details.runtime is None


def test_error_may_carry_data_and_a_numeric_code():
    body = json.dumps(
        {
            "status": "error",
            "message": "timed out",
            "code": 7,
            "data": {"output": ["partial"], "format": "text/plain"},
        }
    ).encode()
    error = decode_response(504, body)
    assert isinstance(error, Error)
    assert error.code == 7
    assert error.data == {"output": ["partial"], "format": "text/plain"}
    assert error.http_consistent


@pytest.mark.parametrize("status", ["Success", "ok", "", None, 1, ["success"]])
def test_status_unknown_refused(status):
    body = json.dumps({"status": status, "data": {}}).encode()
    with pytest.raises(ResponseError, match="status"):
        decode_response(200, body)


def test_missing_status_refused():
    with pytest.raises(ResponseError, match="status"):
        decode_response(200, b'{"data": {}}')


@pytest.mark.parametrize("status", ["success", "fail"])
def test_success_without_data_refused(status):
    body = json.dumps({"status": status}).encode()
    with pytest.raises(ResponseError, match="data"):
        decode_response(200, body)


@pytest.mark.parametrize("data", [[], "x", 1, None])
def test_data_must_be_an_object(data):
    body = json.dumps({"status": "success", "data": data}).encode()
    with pytest.raises(ResponseError, match="object"):
        decode_response(200, body)


@pytest.mark.parametrize("missing", ["performed_at", "runtime"])
def test_missing_performed_at_or_runtime_refused(missing):
    data = {"performed_at": "2014-10-15T17:15:34Z", "runtime": 1, "output": []}
    del data[missing]
    with pytest.raises(ResponseError, match="performed_at or runtime"):
        decode_response(200, json.dumps({"status": "success", "data": data}).encode())


@pytest.mark.parametrize(
    "stamp",
    [
        "yesterday",
        "2014-10-15",
        "2014-10-15T17:15:34",
        "2014-10-15T17:15:34+02:00",
        1413393334,
        None,
    ],
)
def test_performed_at_must_be_iso_8601_utc(stamp):
    data = {"performed_at": stamp, "runtime": 1}
    with pytest.raises(ResponseError):
        decode_response(200, json.dumps({"status": "success", "data": data}).encode())


@pytest.mark.parametrize("runtime", [True, "2.63", None, -1, [1]])
def test_runtime_must_be_number_not_bool(runtime):
    data = {"performed_at": "2014-10-15T17:15:34Z", "runtime": runtime}
    with pytest.raises(ResponseError, match="runtime"):
        decode_response(200, json.dumps({"status": "success", "data": data}).encode())


@pytest.mark.parametrize("message", [None, "", 5, ["x"]])
def test_error_without_message_refused(message):
    body = json.dumps({"status": "error", "message": message}).encode()
    with pytest.raises(ResponseError, match="message"):
        decode_response(500, body)
    with pytest.raises(ResponseError, match="message"):
        decode_response(500, b'{"status": "error"}')


def test_error_code_must_be_a_number():
    for code in (True, "7", [7]):
        body = json.dumps({"status": "error", "message": "x", "code": code}).encode()
        with pytest.raises(ResponseError, match="code"):
            decode_response(500, body)


def test_output_string_list_or_other():
    base = {"performed_at": "2014-10-15T17:15:34Z", "runtime": 1}

    def reply(**extra):
        body = json.dumps({"status": "success", "data": {**base, **extra}}).encode()
        decoded = decode_response(200, body)
        assert isinstance(decoded, Success)
        return decoded

    assert reply(output=["a", "b"]).lines() == ("a", "b")
    assert reply(output="one line").lines() == ("one line",)
    assert reply(output=[]).lines() == ()
    assert reply().lines() == ()  # sec. 2.3.1 para 5: output might even be blank
    assert reply().format == "text/plain"  # para 6: defaults when missing
    structured = reply(output={"yang": 1}, format="application/yang")
    with pytest.raises(ResponseError, match="not text"):
        structured.lines()
    assert structured.data["output"] == {"yang": 1}
    with pytest.raises(ResponseError, match="not text"):
        reply(output=["a", 2]).lines()


def test_extra_members_in_data_are_kept():
    # Sec. 2.3.1 para 7: more information may be added inside "data".
    data = {"performed_at": "2014-10-15T17:15:34Z", "runtime": 1, "min": 40, "avg": 41}
    decoded = decode_response(200, json.dumps({"status": "success", "data": data}).encode())
    assert decoded.data["avg"] == 41


def test_duplicate_keys_refused():
    body = b'{"status": "success", "status": "error", "message": "x"}'
    with pytest.raises(ResponseError, match="duplicate"):
        decode_response(200, body)
    nested = (
        b'{"status": "success", "data": {"runtime": 1, "runtime": 2, '
        b'"performed_at": "2014-10-15T17:15:34Z"}}'
    )
    with pytest.raises(ResponseError, match="duplicate"):
        decode_response(200, nested)


@pytest.mark.parametrize("constant", [b"NaN", b"Infinity", b"-Infinity"])
def test_nan_refused(constant):
    body = (
        b'{"status": "success", "data": {"performed_at": "2014-10-15T17:15:34Z", "runtime": '
        + constant
        + b"}}"
    )
    with pytest.raises(ResponseError):
        decode_response(200, body)


def test_oversized_body_refused_before_parse():
    # Not JSON at all: if it were parsed first the error would say "not valid JSON".
    with pytest.raises(ResponseError, match="over the 16 limit"):
        decode_response(200, b"x" * 17, max_body=16)
    assert protocol.MAX_BODY == 1_048_576


@pytest.mark.parametrize(
    "body", [b"\xff\xfe{}", b"\xc3\x28", b"[1, 2]", b'"success"', b"", b"{", b"null"]
)
def test_non_utf8_or_non_object_body_refused(body):
    with pytest.raises(ResponseError):
        decode_response(200, body)


def test_deeply_nested_body_is_refused_not_crashed():
    with pytest.raises(ResponseError):
        decode_response(200, b"[" * 100000)


def test_body_must_be_bytes():
    with pytest.raises(TypeError):
        decode_response(200, '{"status": "error", "message": "x"}')


def test_http_status_disagreement_recorded():
    """Sec. 4 para 2: rely on the status field in the body, not on the HTTP code."""
    success_on_500 = decode_response(500, SECTION_2_3_1)
    assert isinstance(success_on_500, Success)
    assert success_on_500.http_status == 500
    assert not success_on_500.http_consistent
    error_on_200 = decode_response(200, SECTION_2_3_3)
    assert isinstance(error_on_200, Error)
    assert not error_on_200.http_consistent
    assert decode_response(502, SECTION_2_3_3).http_consistent
    assert not decode_response(404, SECTION_2_3_3).http_consistent
