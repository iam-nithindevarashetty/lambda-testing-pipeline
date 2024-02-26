import requests
import json
from datetime import datetime, timedelta
from pytz import timezone
from elasticsearch import Elasticsearch, helpers
import time
import os
import csv
import traceback
import sys
import creds

def push_elastic(all_records, type):
    try:
        print(all_records,type)
        client = Elasticsearch(
            cloud_id=creds.elastic_cloudid,
            basic_auth=creds.elastic_password
        )
        if type is None:
            resp = client.index(index=creds.elastic_indexname, document=all_records)
            print(resp['result'])
        elif type == "mom":
            resp = client.index(index="maaps_prod_snow_changemanagement_mom", document=all_records)
            print(resp['result'])
        elif type == "data":
            actions = []
            for event in all_records:
                if event['start_date'] == "":
                    del event['start_date']
                data = {
                        "_op_type": "create",
                        "_index": creds.elastic_indexname,
                        "_source": event
                        }
                actions.append(data)
            success, failed = helpers.bulk(client, actions, index=creds.elastic_indexname, raise_on_error=False)
            print(success,failed)
            for error in failed:
                print(error)

    except Exception as e:
        print("Error in push_elastic block:", e)

def get_access_token():
    try:
        token_url = f"https://login.microsoftonline.com/{creds.token_tenant_id}/oauth2/v2.0/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": creds.token_client_id,
            "client_secret": creds.token_client_secret,
            "scope": creds.token_scope,
        }
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()  # Raise an error for non-200 response codes

        token_data = response.json()
        access_token = token_data.get("access_token")
        return access_token
    except requests.exceptions.HTTPError as errh:
        print ("HTTP Error:", errh)
        # record = {'api': 'token', 'message': errh.args[0]}
        # push_elastic(record, type="mom")
        # os._exit(0)
    except Exception as e:
        print("Error in get_access_token block:", e)

def get_change_data(token, offset, create_date, stop_date):
    try:
        change_url = creds.change_management_url
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        params = {
            "sysparm_display_value": "true",
            "sysparm_fields": "number,short_description,type,u_environment,state,start_date,end_date,close_code,business_service,u_outage_indicator,parent,priority,cab_date,cab_required,closed_at,cmdb_ci,service_offering,urgency,justification,implementation_plan,risk_impact_analysis,backout_plan,test_plan,work_start,work_end,business_service.parent,business_service.parent.parent",
            "sysparm_limit": creds.sysparm_limit,
            "sysparm_offset": offset,
            "sysparm_query": f"start_dateBETWEEN{create_date}@{stop_date}%252000:00:00@23:59:59%2520ORDERBYsys_updated_on:desc",
        }
        print(f"Headers - {headers} and Params - {params}")
        response = requests.get(change_url, headers=headers, params=params, verify=False)
        print(f"URL - {response.url}")
        print(f"Response Received - {response}")
        response.raise_for_status()  # Raise an error for non-200 response codes

        change_data = response.json()
        return change_data.get('result', [])
    except requests.exceptions.HTTPError as errh:
        print ("HTTP Error:", errh)
        # if errh.response.status_code == 401:
        #     print("\n\nUnauthorized Access! Check your credentials.")
        #     sys.exit(-1)
        # else:
        #     raise errh
        # record = {'api': 'change management', 'message': errh.args[0]}
        # push_elastic(record, type="mom")
        # os._exit(0)
    except Exception as e:
        print("Error in get_change_data block:", e)

def parse_data(all_records, runtime):
    try:
        transformed_data = []
        for record in all_records:
            record['business_service_parent_parent'] = record['business_service.parent.parent']
            record['business_service_parent'] = record['business_service.parent']
            record['change_id'] = record['number']
            record['Service'] = record['business_service']
            del record['business_service.parent.parent'],record['business_service.parent'],record['number'],record['business_service']
            transformed_record = {}
            for field, field_data in record.items():
                if 'display_value' in field_data:
                    transformed_record[field] = field_data['display_value']
                else:
                    transformed_record[field] = field_data
            transformed_record['@timestamp'] = runtime
            transformed_record.update({
                'Application Name' : 'SNOW',
                'Monitoring Type' : 'change_management_data',
                'Environment Type' : 'Prod',
                'monitoring_kpi' : 'snow-change'
            })
            transformed_data.append(transformed_record)
        return transformed_data
    except Exception as e:
        print("Error in parse_data block:", e)

def get_output(all_records):
    try:
        mapping = {}
        with open(creds.mapping_csv_file_path, 'r') as csv_file:
            csv_reader = csv.reader(csv_file)
            for row in csv_reader:
                Service = row[0]
                mapping[Service] = {
                    "Platform": row[2],
                    "Tribe": row[1],
                    "Company": row[3]
                }
        for item in all_records:
            Service = item.get('Service', '')
            if Service in mapping:
                item.update({
                    "Platform": mapping[Service]['Platform'],
                    "Tribe": mapping[Service]['Tribe'],
                    "Company": mapping[Service]['Company']
                })
        return all_records
    except Exception as e:
        print("Error in get_output block:", e)


def lambda_handler(event, context):
    try:
        runtime = datetime.now(timezone('CET'))
        print(f"Execution Time : {runtime}")
        start = time.time()
        access_token = get_access_token()
        stop_date = datetime.now(timezone('CET'))
        create_date = stop_date - timedelta(days=creds.fetch_period)
        offset = 0
        all_records = []

        while True:
            change_data = get_change_data(access_token, offset, create_date, stop_date)
            all_records.extend(change_data)
            offset += len(change_data)
            if len(change_data) < creds.sysparm_limit:
                break
        all_records = parse_data(all_records, runtime)
        all_records = get_output(all_records)
        push_elastic(all_records, type="data")
        end = time.time()
        execution_time = end - start
        exc_details = {'@timestamp': runtime, 'execution_time_for_change_in_secs': execution_time, 'last run': runtime}
        push_elastic(exc_details, type=None)

        return {
            'statusCode': 200,
            'body': json.dumps('Success')
        }
    except Exception as e:
        print("Error in lambda_handler:", e)
        # Log the error
        return {
            'statusCode': 500,
            'body': json.dumps('Error')
        }

if __name__ == "__main__":
    lambda_handler(event=None,context=None)