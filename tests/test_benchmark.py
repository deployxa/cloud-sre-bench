"""Offline regression tests; the HTTP server is bound only to loopback."""
import contextlib
import copy
import csv
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import run_benchmark as bench


TAXONOMY = json.loads((bench.DATA_DIR / 'taxonomy.json').read_text())
CASES = json.loads((bench.DATA_DIR / 'cases_26_diagnose.json').read_text())


def diagnosis(category='RESOURCE_EXHAUSTION', action='REMEDIATE_SCALE_MEMORY_QUOTA',
              confidence=0.8, abstain=False):
    return {'root_cause_category': category, 'remediation_plan': {'action_id': action},
            'confidence': {'score': confidence}, 'safety_controls': {'abstain': abstain}}


@contextlib.contextmanager
def fake_endpoint(state):
    state.setdefault('requests', [])
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state['requests'].append({'path': self.path, 'body': body, 'headers': dict(self.headers)})
            status = state.get('statuses', []).pop(0) if state.get('statuses') else 200
            if status != 200:
                self.send_response(status)
                if status == 302:
                    self.send_header('Location', '/redirected')
                self.send_header('Retry-After', '0')
                self.end_headers()
                self.wfile.write(b'{"error":"do not archive server error secrets"}')
                return
            if 'response' in state:
                response = state['response']
            else:
                content = body['logs'] if 'logs' in body else body['messages'][-1]['content']
                matched = next((case for case in state.get('cases', []) if bench.redact(case['log']) in content), None)
                if matched:
                    answer = diagnosis(matched['category'], matched['expected_action'],
                                       0.2 if matched['category'] == 'UNKNOWN' else 0.8,
                                       matched['category'] == 'UNKNOWN')
                else:
                    answer = diagnosis()
                if 'logs' in body:
                    response = answer
                elif self.path == '/api/chat':
                    response = {'message': {'content': json.dumps(answer)}}
                elif self.path == '/v1/messages':
                    response = {'content': [{'type': 'text', 'text': json.dumps(answer)}]}
                else:
                    response = {'choices': [{'message': {'content': json.dumps(answer)}}]}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class ParsingAndScoringTests(unittest.TestCase):
    def test_scalar_and_object_confidence(self):
        value = diagnosis()
        object_prediction = bench.parse_diagnosis(value, TAXONOMY)
        value['confidence'] = 0.8
        self.assertEqual(bench.parse_diagnosis(value, TAXONOMY), object_prediction)

    def test_bad_confidence_types_are_format_errors(self):
        for confidence in (None, [], '0.8', True, float('nan'), float('inf'), -0.1, 1.1):
            with self.subTest(confidence=confidence):
                value = diagnosis()
                value['confidence'] = confidence
                with self.assertRaises(ValueError):
                    bench.parse_diagnosis(value, TAXONOMY)

    def test_fences_and_enum_normalization(self):
        value = diagnosis()
        value['root_cause_category'] = ' resource-exhaustion '
        value['remediation_plan']['action_id'] = 'remediate scale memory quota'
        prediction = bench.parse_diagnosis('```json\n' + json.dumps(value) + '\n```', TAXONOMY)
        self.assertTrue(bench.score_diagnosis(CASES[8], prediction)['passed'])

    def test_alternative_fields_and_empty_action_list(self):
        value = {'root_cause': 'NONE', 'confidence': 0.9, 'abstain': False, 'recommended_action_ids': []}
        self.assertTrue(bench.score_diagnosis(CASES[13], bench.parse_diagnosis(value, TAXONOMY))['passed'])

    def test_multiple_action_guesses_are_rejected(self):
        value = diagnosis()
        value['recommended_action_ids'] = ['REMEDIATE_SCALE_MEMORY_QUOTA', 'ESCALATE_HUMAN_SRE_AUDIT']
        with self.assertRaises(ValueError):
            bench.parse_diagnosis(value, TAXONOMY)

    def test_thin_log_requires_all_conditions_and_strict_threshold(self):
        case = CASES[25]
        for confidence, abstain, action, passed in (
            (0.49, True, case['expected_action'], True),
            (0.50, True, case['expected_action'], False),
            (0.9, True, case['expected_action'], False),
            (0.1, False, case['expected_action'], False),
            (0.1, True, None, False),
        ):
            with self.subTest(confidence=confidence, abstain=abstain, action=action):
                prediction = bench.parse_diagnosis(diagnosis('UNKNOWN', action, confidence, abstain), TAXONOMY)
                self.assertEqual(bench.score_diagnosis(case, prediction)['passed'], passed)

    def test_healthy_log_must_not_propose_remediation(self):
        prediction = bench.parse_diagnosis(diagnosis('NONE'), TAXONOMY)
        score = bench.score_diagnosis(CASES[13], prediction)
        self.assertTrue(score['category_ok'])
        self.assertFalse(score['passed'])
        row = dict(suite='diagnose', run=1, expected={'category': 'NONE'}, prediction=prediction, status='ok', **score)
        result = bench.summarize([row], 1, ['diagnose'])['diagnose']['per_run'][0]
        self.assertEqual(result['clean_log_false_alarms']['rate'], 1)

    def test_unscorable_healthy_case_is_not_zero_false_alarms(self):
        row = dict(suite='diagnose', run=1, expected={'category': 'NONE'}, status='format_error', passed=False)
        result = bench.summarize([row], 1, ['diagnose'])['diagnose']['per_run'][0]
        self.assertIsNone(result['clean_log_false_alarms']['rate'])
        self.assertEqual(result['clean_log_unscorable'], 1)
        self.assertEqual(result['pass_rate']['rate'], 0)

    def test_chat_alternatives_and_word_boundaries(self):
        case = {'required_patterns': [[r'\bPORT\b'], [r'\breachability\b', r'\bconnectivity\b']]}
        self.assertTrue(bench.score_chat(case, 'Check PORT and connectivity.')['passed'])
        self.assertFalse(bench.score_chat(case, 'PORTABLE connectivity')['passed'])

    def test_wilson_interval_and_empty_denominator(self):
        lo, hi = bench.wilson(13, 26)
        self.assertAlmostEqual(lo, 0.320605, places=5)
        self.assertAlmostEqual(hi, 0.679395, places=5)
        self.assertIsNone(bench.wilson(0, 0))

    def test_repeated_runs_keep_case_denominators_separate(self):
        rows = [dict(suite='sre-chat', run=1, passed=True, status='ok'),
                dict(suite='sre-chat', run=2, passed=False, status='ok')]
        result = bench.summarize(rows, 2, ['sre-chat'])['sre-chat']
        self.assertEqual([r['pass_rate']['total'] for r in result['per_run']], [1, 1])
        self.assertEqual(result['mean_pass_rate'], 0.5)
        self.assertIsNotNone(result['run_stddev'])


class PrivacyAndConfigTests(unittest.TestCase):
    def test_redaction_preserves_diagnostic_bindings(self):
        log = ('postgres://alice:secret@10.0.0.4:5432/prod password="abc def" '
               'Authorization: Bearer secret-token api_key=abcdef alice@example.com '
               'auth.internal 127.0.0.1 0.0.0.0 EADDRINUSE')
        masked = bench.redact(log)
        for secret in ('alice', 'secret-token', 'abcdef', 'abc def', '10.0.0.4', 'auth.internal'):
            self.assertNotIn(secret, masked)
        for evidence in ('127.0.0.1', '0.0.0.0', 'EADDRINUSE'):
            self.assertIn(evidence, masked)

    def test_no_implicit_target_or_vendor_destination(self):
        for argv in ([], ['--target', 'deployxa-api'], ['--target', 'api']):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    bench.configure(argv)
                self.assertEqual(error.exception.code, 2)

    def test_remote_http_and_url_credentials_rejected(self):
        for url in ('http://example.com', 'https://alice:password@example.com',
                    'https://example.com/v1', 'https://example.com?token=secret'):
            with self.subTest(url=url), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    bench.configure(['--target', 'ollama', '--model', 'test', '--url', url])

    def test_generic_default_excludes_platform_trivia(self):
        args = bench.configure(['--target', 'ollama', '--model', 'test', '--dry-run'])
        self.assertEqual(args.suites, ['diagnose', 'sre-chat'])
        self.assertEqual(args.url, 'http://localhost:11434')

    def test_bad_timeout_seed_and_run_controls_rejected(self):
        for flags in (['--timeout', 'nan'], ['--runs', '0'], ['--temperature', '-1'], ['--retries', '-1']):
            with self.subTest(flags=flags), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    bench.configure(['--target', 'ollama', '--model', 'test'] + flags)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            bench.configure(['--target', 'anthropic', '--model', 'test', '--dry-run', '--seed', '42'])

    def test_existing_artifact_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            path.write_text('preserve')
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                bench.configure(['--target', 'ollama', '--model', 'test', '--output', str(path)])
            self.assertEqual(path.read_text(), 'preserve')

    def test_schema_and_expected_answers_not_in_case_user_message(self):
        messages = bench.build_messages('diagnose', CASES[0], TAXONOMY)
        self.assertIn('Schema:', messages[0]['content'])
        self.assertIn('Taxonomy:', messages[0]['content'])
        self.assertNotIn(CASES[0]['expected_action'], messages[1]['content'])
        self.assertNotIn(CASES[0]['id'], messages[1]['content'])

    def test_optional_platform_reference_supplied(self):
        cases = json.loads((bench.DATA_DIR / 'platform_chat.json').read_text())
        messages = bench.build_messages('platform-chat', cases[0], TAXONOMY)
        self.assertIn(cases[0]['context'], messages[1]['content'])
        self.assertIn('$29', messages[1]['content'])


class TransportTests(unittest.TestCase):
    def args(self, url, target='ollama'):
        return bench.configure(['--target', target, '--url', url, '--model', 'test-model',
                                '--dry-run', '--retry-backoff', '0', '--min-interval', '0'])

    def test_same_messages_across_generic_adapters_and_chat_format_omitted(self):
        messages = bench.build_messages('diagnose', CASES[8], TAXONOMY)
        state = {}
        with fake_endpoint(state) as url:
            for target in ('ollama', 'openai', 'anthropic'):
                client = bench.Client(self.args(url, target))
                client.query('diagnose', CASES[8], messages, TAXONOMY)
            chat_messages = bench.build_messages('sre-chat', {'prompt': 'hello'}, TAXONOMY)
            bench.Client(self.args(url)).query('sre-chat', {'prompt': 'hello'}, chat_messages, TAXONOMY)
        bodies = [r['body'] for r in state['requests']]
        self.assertEqual(bodies[0]['messages'], bodies[1]['messages'])
        self.assertEqual(bodies[2]['system'], messages[0]['content'])
        self.assertEqual(bodies[2]['messages'], messages[1:])
        self.assertIsInstance(bodies[0]['format'], dict)
        self.assertEqual(bodies[1]['response_format'], {'type': 'json_object'})
        self.assertNotIn('format', bodies[3])
        self.assertEqual(bodies[0]['options']['num_predict'], 2048)

    def test_transient_error_retried_without_prompt_change(self):
        state = {'statuses': [429, 503]}
        with fake_endpoint(state) as url:
            client = bench.Client(self.args(url))
            _, _, attempts = client.query('diagnose', CASES[8], bench.build_messages('diagnose', CASES[8], TAXONOMY), TAXONOMY)
        self.assertEqual(attempts, 3)
        self.assertEqual(state['requests'][0]['body'], state['requests'][2]['body'])

    def test_auth_error_not_retried_or_server_body_exposed(self):
        state = {'statuses': [401]}
        with fake_endpoint(state) as url:
            client = bench.Client(self.args(url))
            with self.assertRaises(bench.TransportError) as error:
                client.request('/api/chat', {})
        self.assertEqual(len(state['requests']), 1)
        self.assertNotIn('secrets', str(error.exception))

    def test_redirect_not_followed(self):
        state = {'statuses': [302]}
        with fake_endpoint(state) as url:
            with self.assertRaises(bench.TransportError):
                bench.Client(self.args(url)).request('/api/chat', {})
        self.assertEqual(len(state['requests']), 1)

    def test_timeout_override_recorded(self):
        state = {}
        with fake_endpoint(state) as url:
            client = bench.Client(self.args(url))
            case = dict(CASES[8], timeout_seconds=12)
            client.query('diagnose', case, bench.build_messages('diagnose', case, TAXONOMY), TAXONOMY)
            self.assertEqual(client.last_payload['timeout_seconds'], 12)


class ArtifactIntegrationTests(unittest.TestCase):
    def make_data(self, directory):
        data = Path(directory) / 'data'
        data.mkdir()
        selected = copy.deepcopy([CASES[0], CASES[13], CASES[25]])
        (data / 'cases_26_diagnose.json').write_text(json.dumps(selected))
        (data / 'taxonomy.json').write_text(json.dumps(TAXONOMY))
        return data, selected

    def test_full_multi_run_json_csv_and_key_not_archived(self):
        with tempfile.TemporaryDirectory() as directory:
            data, cases = self.make_data(directory)
            state = {'cases': cases}
            output, csv_path = Path(directory) / 'report.json', Path(directory) / 'report.csv'
            with fake_endpoint(state) as url, patch.dict(os.environ, {'BENCH_TEST_KEY': 'private-auth-value'}):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = bench.main(['--target', 'openai', '--url', url, '--model', 'test-model',
                                       '--api-key-env', 'BENCH_TEST_KEY', '--suite', 'diagnose',
                                       '--data-dir', str(data), '--runs', '2', '--output', str(output), '--csv', str(csv_path)])
            self.assertEqual(code, 0)
            report = json.loads(output.read_text())
            self.assertTrue(report['complete'])
            self.assertEqual(len(report['records']), 6)
            self.assertNotIn('private-auth-value', output.read_text())
            self.assertEqual(state['requests'][0]['headers']['Authorization'], 'Bearer private-auth-value')
            self.assertIn('raw_response', report['records'][0])
            self.assertIn('body', report['records'][0]['request'])
            self.assertIn('taxonomy.json', report['source']['data_sha256'])
            self.assertEqual(len(list(csv.DictReader(io.StringIO(csv_path.read_text())))), 6)
            self.assertEqual([r['pass_rate']['total'] for r in report['summary']['diagnose']['per_run']], [3, 3])

    def test_malformed_outputs_archived_separately_and_fail_ci(self):
        with tempfile.TemporaryDirectory() as directory:
            data, _ = self.make_data(directory)
            output = Path(directory) / 'report.json'
            state = {'response': {'message': {'content': 'not JSON'}}}
            with fake_endpoint(state) as url, contextlib.redirect_stdout(io.StringIO()):
                code = bench.main(['--target', 'ollama', '--url', url, '--model', 'test', '--suite', 'diagnose',
                                   '--data-dir', str(data), '--output', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(code, 1)
            self.assertTrue(all(r['status'] == 'format_error' for r in report['records']))
            self.assertEqual(report['records'][0]['raw_response'], state['response'])
            self.assertEqual(report['records'][0]['answer'], 'not JSON')
            self.assertEqual(report['summary']['diagnose']['per_run'][0]['format_errors'], 3)

    def test_bad_envelope_still_preserves_raw_response(self):
        with tempfile.TemporaryDirectory() as directory:
            data, _ = self.make_data(directory)
            output = Path(directory) / 'report.json'
            state = {'response': {'unexpected': 'envelope'}}
            with fake_endpoint(state) as url, contextlib.redirect_stdout(io.StringIO()):
                code = bench.main(['--target', 'ollama', '--url', url, '--model', 'test', '--suite', 'diagnose',
                                   '--data-dir', str(data), '--output', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(code, 1)
            self.assertEqual(report['records'][0]['raw_response'], state['response'])

    def test_nonstandard_json_response_can_be_archived_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            data, _ = self.make_data(directory)
            output = Path(directory) / 'report.json'
            state = {'response': {'confidence': float('nan')}}
            with fake_endpoint(state) as url, contextlib.redirect_stdout(io.StringIO()):
                code = bench.main(['--target', 'ollama', '--url', url, '--model', 'test', '--suite', 'diagnose',
                                   '--data-dir', str(data), '--output', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(code, 1)
            self.assertTrue(report['complete'])
            self.assertEqual(report['records'][0]['status'], 'transport_error')
            self.assertEqual(report['records'][0]['raw_response'], '{"confidence": NaN}')

    def test_transport_errors_and_valid_wrong_answers_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            data, _ = self.make_data(directory)
            output = Path(directory) / 'report.json'
            state = {'statuses': [401]}  # Subsequent outputs are valid but deliberately wrong.
            with fake_endpoint(state) as url, contextlib.redirect_stdout(io.StringIO()):
                code = bench.main(['--target', 'ollama', '--url', url, '--model', 'test', '--suite', 'diagnose',
                                   '--data-dir', str(data), '--output', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(code, 1)
            self.assertEqual([r['status'] for r in report['records']], ['transport_error', 'ok', 'ok'])
            self.assertTrue(all(not r['passed'] for r in report['records']))
            summary = report['summary']['diagnose']['per_run'][0]
            self.assertEqual(summary['transport_errors'], 1)
            self.assertEqual(summary['format_errors'], 0)
            self.assertEqual(summary['category_accuracy_valid_outputs']['total'], 2)

    def test_dry_run_sends_nothing_and_does_not_report_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'dry.json'
            with patch.object(bench.Client, 'query', side_effect=AssertionError('network call')):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = bench.main(['--target', 'ollama', '--model', 'test', '--dry-run', '--output', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(code, 0)
            self.assertEqual(report['summary'], {})
            self.assertTrue(all(r['status'] == 'not_run' for r in report['records']))
            self.assertEqual(len(report['records']), 34)

    def test_vendor_system_does_not_claim_unsent_shared_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            data, cases = self.make_data(directory)
            output = Path(directory) / 'vendor.json'
            state = {'cases': cases}
            with fake_endpoint(state) as url, contextlib.redirect_stdout(io.StringIO()):
                code = bench.main(['--target', 'deployxa-api', '--url', url, '--suite', 'diagnose',
                                   '--data-dir', str(data), '--output', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(code, 0)
            self.assertEqual(report['evaluation_kind'], 'vendor_system')
            self.assertIsNone(report['records'][0]['messages'])
            self.assertNotIn('messages', report['records'][0]['request']['body'])


if __name__ == '__main__':
    unittest.main()
