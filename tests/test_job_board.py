"""Offline regression tests: python -m unittest discover -s tests -v."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import job_board as board
import main as app


class JobBoardTests(unittest.TestCase):
    """Exercise selection, deadlines, retries, export, and integration offline."""

    def setUp(self):
        """Keep normal application output out of test results."""
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_manual_login(self):
        """Opening the board still waits for manual login and agreements."""
        driver = Mock()
        with patch.object(board, 'WebDriverWait') as wait, patch.object(board.time, 'sleep'):
            self.assertTrue(board.login_to_hkust(driver))
        driver.get.assert_called_once_with(board.TARGET_URL)
        wait.assert_called_once_with(driver, 300, poll_frequency=1)
        wait.return_value.until.assert_called_once_with(board.final_job_board_loaded)

    def test_board_visibility(self):
        """Missing, hidden, and failing job lists do not complete login."""
        driver = Mock()
        for rows, expected in [([], False), ([Mock(is_displayed=lambda: False)], False),
                               ([Mock(is_displayed=lambda: True)], True)]:
            driver.find_elements.return_value = rows
            self.assertEqual(board.final_job_board_loaded(driver), expected)
        driver.find_elements.side_effect = RuntimeError('not ready')
        self.assertFalse(board.final_job_board_loaded(driver))

    def test_filter_options(self):
        """Empty values and Clear All are excluded, while labels are trimmed."""
        options = [Mock(text=text, get_attribute=Mock(return_value=value))
                   for value, text in [('', 'Placeholder'), ('0', 'Clear All'), ('1', ' Tech ')]]
        driver = Mock()
        driver.find_element.return_value.find_elements.return_value = options
        self.assertEqual(board.get_select_options(driver, 'BN[]'), [{'value': '1', 'name': 'Tech'}])

    def test_selection_validation(self):
        """Invalid formats, limits, ranges, and rejected choices all reprompt."""
        options = [{'value': str(i), 'name': str(i)} for i in range(3)]
        answers = ['bad', '1,2,3', '0,4', '1', 'n', '3,1,3', 'Y']
        with patch('builtins.input', side_effect=answers):
            self.assertEqual(board.choose_multiple_options(options, 'Test', 2), [options[2], options[0]])
        with patch('builtins.input', return_value=''):
            self.assertEqual(board.choose_multiple_options(options, 'Test', 2), [])

    def test_all_filter_mappings_and_limits(self):
        """All seven categories retain their original selectors and limits."""
        cases = [('business_natures', 'BN[]', 10), ('job_natures', 'JN[]', 10),
                 ('employment_types', 'EMT[]', 5), ('working_locations', 'WL[]', 5),
                 ('qualification_levels', 'awards[]', 3), ('employment_modes', 'EM[]', 2),
                 ('languages', 'L[]', 6)]
        for name, selector, limit in cases:
            with self.subTest(name=name), patch.object(board, 'get_select_options', return_value=[]) as get, \
                    patch.object(board, 'choose_multiple_options', return_value=[]) as choose, \
                    patch.object(board, 'apply_select_values') as apply:
                getattr(board, 'choose_' + name)('driver')
                get.assert_called_once_with('driver', selector)
                self.assertEqual(choose.call_args.args[2], limit)
                getattr(board, 'apply_' + name)('driver', ['selected'])
                apply.assert_called_once_with('driver', selector, ['selected'])

    def test_skipped_filter(self):
        """Skipping a filter leaves the webpage untouched."""
        driver = Mock()
        board.apply_select_values(driver, 'BN[]', [])
        self.assertEqual(driver.mock_calls, [])

    def test_deadline_formats_and_status(self):
        """All six date formats and the today/expired/unknown boundaries work."""
        for text in ['2030-03-21', '2030/03/21', '21/03/2030', '21-03-2030',
                     '21 Mar 2030', '21 March 2030']:
            self.assertEqual(board.parse_deadline('Deadline: ' + text), date(2030, 3, 21))
        for text in ['', 'unknown', '2030-02-31']:
            self.assertIsNone(board.parse_deadline(text))
        self.assertEqual(board.get_deadline_status(date.today().isoformat()), 'valid')
        self.assertEqual(board.get_deadline_status((date.today() - timedelta(days=1)).isoformat()), 'expired')
        for text, status in [('Open until filled', 'valid'), ('Closed', 'expired'), ('TBC', 'unknown')]:
            self.assertEqual(board.get_deadline_status(text), status)

    def test_detail_deadline_and_record(self):
        """Deadline labels, header removal, posting date, and Unicode survive export."""
        for text in ['Application Deadline\n2030-03-21', 'Application Deadline: 2030-03-21',
                     'Application Deadline info\nSee below\n2030-03-21']:
            self.assertEqual(board.extract_deadline_from_detail(text), '2030-03-21')
        job = dict(company='公司', job_title_nature='Engineer', application_deadline='2030-03-21',
                   posting_date='2030-03-01')
        result = board.build_job_json(job, 'Header\n2030-03-21\n Build things \n')
        self.assertEqual(result, {'Company/Organization': '公司', 'Job Title/Job Nature': 'Engineer',
                                 'Application Deadline': '2030-03-21',
                                 'Other information': 'Posting Date: 2030-03-01 | Build things'})

    def test_fetch_retries(self):
        """Only failed, empty, and missing replies retry; successful URLs stay done."""
        jobs = [{'url': u} for u in 'abcd']
        responses = [[{'url': 'a', 'ok': True, 'text': 'A'}, {'url': 'b', 'ok': True, 'text': ' '},
                      {'url': 'd', 'ok': False, 'error': 'HTTP 500'}],
                     [{'url': 'b', 'ok': True, 'text': 'B'}, {'url': 'c', 'ok': False, 'error': 'down'}],
                     [{'url': 'c', 'ok': True, 'text': 'C'}, {'url': 'd', 'ok': False, 'error': 'still down'}]]
        with patch.object(board, 'browser_fetch_details', side_effect=responses) as fetch, \
                patch.object(board.time, 'sleep'):
            success, errors = board.fetch_details_with_retries('driver', jobs)
        self.assertEqual(success, dict(a='A', b='B', c='C'))
        self.assertEqual(errors, {'d': 'still down'})
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual({j['url'] for j in fetch.call_args_list[1].args[1]}, {'b', 'c', 'd'})
        self.assertEqual({j['url'] for j in fetch.call_args_list[2].args[1]}, {'c', 'd'})

    def test_page_screening(self):
        """Expired jobs skip fetching; unknown dates require valid details; failures retain valid jobs."""
        jobs = [dict(url=u, company=u, application_deadline=deadline) for u, deadline in
                [('valid', 'until filled'), ('failed', 'until filled'), ('expired', 'closed'),
                 ('unknown', 'TBC'), ('unresolved', 'TBC'), ('detail_expired', 'TBC')]]
        jobs += [dict(jobs[0]), {'url': ''}]
        seen = set()
        with patch.object(board, 'extract_current_page_jobs', return_value=jobs), \
                patch.object(board, 'fetch_details_with_retries', return_value=(
                    {'valid': 'description', 'unknown': 'Application Deadline: until filled\nDetails',
                     'detail_expired': 'Application Deadline: closed'}, {'failed': 'down'})) as fetch:
            result = board.process_current_page('driver', 1, seen)
        self.assertEqual([r['Company/Organization'] for r in result], ['valid', 'failed', 'unknown'])
        self.assertEqual(result[1]['Other information'], 'ERROR while reading job details: down')
        self.assertEqual(result[2]['Application Deadline'], 'until filled')
        self.assertNotIn('expired', [j['url'] for j in fetch.call_args.args[1]])
        self.assertEqual(len(seen), 6)

    def test_json_saving(self):
        """JSON output creates parents and replaces prior contents."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'nested/jobs.json'
            with patch.object(board, 'OUTPUT_FILE', path):
                board.save_json([{'公司': '測試'}])
                self.assertEqual(json.loads(path.read_text()), [{'公司': '測試'}])
                board.save_json([])
                self.assertEqual(json.loads(path.read_text()), [])

    def test_multi_page_export(self):
        """Export resets the file, saves each page, and processes beyond two pages."""
        pages = [[{'page': 1}], [{'page': 2}], [{'page': 3}]]
        snapshots = []
        with patch.object(board, 'WebDriverWait'), \
                patch.object(board, 'process_current_page', side_effect=pages) as process, \
                patch.object(board, 'click_next_page', side_effect=[True, True, False]), \
                patch.object(board, 'get_visible_pagination_text', return_value=[]), \
                patch.object(board, 'save_json', side_effect=lambda rows: snapshots.append(list(rows))):
            self.assertEqual(board.export_jobs_to_json(Mock()), sum(pages, []))
        self.assertEqual([len(s) for s in snapshots], [0, 1, 2, 3])
        self.assertEqual([c.args[1] for c in process.call_args_list], [1, 2, 3])

    def test_pagination_timeout(self):
        """A click without changed rows must not count as a new page."""
        driver = Mock(current_url='board')
        driver.execute_script.return_value = {'clicked': True}
        with patch.object(board, 'get_first_job_url', return_value='same'), \
                patch.object(board, 'WebDriverWait') as wait, patch.object(board.time, 'sleep'):
            wait.return_value.until.side_effect = board.TimeoutException()
            self.assertFalse(board.click_next_page(driver, 1))
        driver.execute_script.return_value = {'clicked': False}
        self.assertFalse(board.click_next_page(driver, 1))

    def test_main_uses_merged_exporter_and_closes_browser(self):
        """The main workflow uses the new module and still closes Chrome after failures."""
        self.assertIs(app.job_exporter, board)
        driver = Mock()
        with patch.object(board, 'OUTPUT_FILE'), patch.object(app, 'create_driver', return_value=driver), \
                patch.object(app, 'login_to_hkust', side_effect=RuntimeError('login stopped')):
            with self.assertRaisesRegex(RuntimeError, 'login stopped'):
                app.main()
            self.assertEqual(board.OUTPUT_FILE, app.INPUT_JSON)
        driver.quit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
