import json
import os
import secrets

import boto3

kinesis = boto3.client('kinesis')
dynamodb = boto3.client('dynamodb')
ssm = boto3.client('ssm')
awslambda = boto3.client('lambda')

LAST_EVALUATED_PARAMETER = '/ddbScanner/lastEvaluatedKey'

def scanner(event, context):
    config = get_config()
    last_evaluated_key = config['last_evaluated_key']

    while True:
        params = {
            'TableName': config['table_name'],
            'Limit': 500
        }
        if last_evaluated_key:
            params['ExclusiveStartKey'] = last_evaluated_key

        resp = dynamodb.scan(**params)
        records = []
        for item in resp['Items']:
            records.append({
                'Data': json.dumps(item),
                'PartitionKey': secrets.token_hex(12) # Partition key shouldn't matter much here.
            })

        put_records(config['stream_name'], records)

        if 'LastEvaluatedKey' not in resp:
            # Scan is complete. Time to finish.
            break
        ssm.put_parameter(
            Name=LAST_EVALUATED_PARAMETER,
            Value=json.dumps(resp['LastEvaluatedKey']),
            Type='String',
            Overwrite=True
        )
        last_evaluated_key = resp['LastEvaluatedKey']

        if context.get_remaining_time_in_millis() < 10000:
            awslambda.invoke(
                FunctionName=context.function_name,
                InvocationType='Event',
            )
            return

    print('Scan complete!')
    return


def get_config():
    table_arn = os.environ['TABLE_ARN']
    table_name = table_arn.split('/')[1]
    stream_arn = os.environ['STREAM_ARN']
    stream_name = stream_arn.split('/')[1]

    try:
        resp = ssm.get_parameter(
            Name=LAST_EVALUATED_PARAMETER
        )
        last_evaluated_key = json.loads(resp['Parameter']['Value'])
    except ssm.exceptions.ParameterNotFound:
        last_evaluated_key = ''

    return {
        'table_name': table_name,
        'stream_name': stream_name,
        'last_evaluated_key': last_evaluated_key
    }


def put_records(stream_name, records):
    resp = kinesis.put_records(
        Records=records,
        StreamName=stream_name
    )

    if resp['FailedRecordCount'] == 0:
        return 

    failed_records = []
    for i, record in enumerate(resp['Records']):
        if 'ErrorCode' in record:
            failed_records.append(records[i])

    return put_records(stream_name, failed_records)
