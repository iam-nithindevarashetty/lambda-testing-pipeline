import unittest
from unittest.mock import patch, MagicMock, Mock
import requests
import time
from datetime import datetime, timedelta
from pytz import timezone
from main_code import *
import creds

start = time.time()
end = time.time()
execution_time = end - start
stop_date = datetime.now(timezone('CET'))
create_date = stop_date - timedelta(days=creds.fetch_period)
runtime = datetime.now(timezone('CET'))



class TestMainCode(unittest.TestCase):

    @patch('main_code.requests.post')
    def test_get_access_token_success(self, mock_post):
        mock_response = Mock()
        # mock_response.status_code = 200
        mock_post.return_value.json.return_value = {'access_token': 'mocked_token'}
        result = get_access_token()
        self.assertEqual(result, 'mocked_token')

    @patch('requests.post')
    def test_get_access_token_failure(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
  

    @patch('main_code.requests.get')
    def test_get_change_data_success(self, mock_get):
        mock_get.return_value.json.return_value = {'result': [{'change_data': 'mocked_value'}]}
        result = get_change_data('mocked_token', 0, create_date, stop_date)
        self.assertEqual(result, [{'change_data': 'mocked_value'}])
   
    @patch('requests.get')
    def test_get_change_data_success_url(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        # mock_response.json.return_value = {'result': [{'change_data': 'example'}]}
        mock_get.return_value = mock_response

    @patch('main_code.requests.get')
    def test_get_change_data_failure(self, mock_get):
        mock_response = Mock()
        mock_get.return_value = mock_response


    def test_parse_data(self):
        # Create sample data for testing
        sample_data = [{'number': '123', 'business_service': 'SampleService'}]
        # Call the function with your sample data
        result = parse_data(sample_data, '2024-02-26T10:35:32+05:30')
        # Define the expected transformed data based on your parsing logic
        expected_result = [{'change_id': '123', 'Service': 'SampleService', '@timestamp': '2024-02-26T10:35:32+05:30', 'Application Name': 'SNOW', 'Monitoring Type': 'change_management_data', 'Environment Type': 'Prod', 'monitoring_kpi': 'snow-change'}]
        # Assert that the function returned the expected result
        self.assertEqual(result, expected_result)


if __name__ == '__main__':
    unittest.main()
