import boto3
import click

client = boto3.client('dynamodb', region_name='us-east-1')

@click.command()
@click.option('--count', help="Number of items to insert", type=int, required=True)
def insert_items(count):
    for i in range(count):
        client.put_item(
            TableName='scanner-test-table',
            Item={
                "Id": { "S": str(i) }
            }
        )

    print("Inserted {count} items to table".format(count=count))


if __name__ == "__main__":
    insert_items()
