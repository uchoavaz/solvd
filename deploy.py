from botocore.client import ClientError
from pathlib import Path
import boto3
import time
import json
import sys
import os

class DeploySolvDTest():
    def __init__(self, region, stack_name, s3_bucket, aws_access_key_id, aws_secret_access_key):
        self.stack_name = stack_name
        self.s3_bucket = s3_bucket
        self.region = region
        self.stack_name = stack_name
        self.bucket_url = "https://{}.s3.amazonaws.com".format(s3_bucket)
        self.url_nested_controller = self.bucket_url + "/controller.yml"
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.cloudformation_client = boto3.client(
            'cloudformation',
            region_name=self.region,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key
        )
        self.s3_client = boto3.resource(
            's3',
            region_name=self.region,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key
        )

    def get_stack_status(self):
        client = self.cloudformation_client
        completed = False
        rollback_in_progress_check = False
        json_stack_status = {}
        while not completed:

            response = client.describe_stacks(StackName=self.stack_name)
            response = response['Stacks'][0]['StackStatus']
            json_stack_status['stack_status'] = response
            json_stack_status['stack_name'] = self.stack_name

            ### This logic is to make the script stop getting info from the stack because it could reach in the desired state
            if (('CREATE_COMPLETE' in response or 'UPDATE_COMPLETE' in response or 
                 'UPDATE_ROLLBACK_COMPLETE' in response or 'ROLLBACK_COMPLETE' in response) and 
                 'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS' not in response):
                
                completed = True

            elif (('ROLLBACK_IN_PROGRESS' in response or 
                   'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS' in response or 
                   'UPDATE_ROLLBACK_IN_PROGRESS' in response) and not rollback_in_progress_check):

                ### This logic above is to loop all failed creations from the host stack
                rollback_response = client.describe_stack_events(StackName=self.stack_name)
                for event in rollback_response['StackEvents']:
                    if 'CREATE_FAILED' in event['ResourceStatus'] or 'UPDATE_FAILED' in event['ResourceStatus']:
                        json_stack_status['nested_failed_stacks'] = []
                        if 'Embedded' in event['ResourceStatusReason']:
                            json_stack_status['nested_failed_stacks'].append(
                                {
                                    'nested_stack_id': event['PhysicalResourceId'],
                                    'nested_failed_stack_events': []
                                }
                            )

                            ### This logic above is to loop all failed creations from the nested stack
                            embedded_events = client.describe_stack_events(StackName=event['PhysicalResourceId'])
                            for embedded_event in embedded_events['StackEvents']:
                                if ('CREATE_FAILED' in embedded_event['ResourceStatus'] or 
                                    'UPDATE_FAILED' in embedded_event['ResourceStatus']):
                                    if 'The following resource' not in embedded_event['ResourceStatusReason']:
                                        index = len(json_stack_status['nested_failed_stacks']) - 1
                                        nested_stack_events_dict = {
                                                'nested_stack_status_reason': embedded_event['ResourceStatusReason'],
                                                'nested_stack_physical_resource_id': embedded_event['PhysicalResourceId']
                                            }
                                        if (nested_stack_events_dict not in 
                                            json_stack_status['nested_failed_stacks'][index]['nested_failed_stack_events']):
                                            json_stack_status['nested_failed_stacks'][index]['nested_failed_stack_events'].append(
                                                nested_stack_events_dict
                                            )
                rollback_in_progress_check = True

            print("\n" + json.dumps(json_stack_status))
            time.sleep(15)

    ### This function will create a new stack
    def create_stack(self):
        client = self.cloudformation_client
        try:
            client.create_stack(
                    StackName=self.stack_name,
                    TemplateURL= self.url_nested_controller,
                    Parameters=[
                        {"ParameterKey": "App",
                            "ParameterValue": self.stack_name},
                        {"ParameterKey": "StackUrl",
                            "ParameterValue": self.bucket_url},
                    ],
                    Capabilities=['CAPABILITY_NAMED_IAM'],       
            )
        except client.exceptions.AlreadyExistsException as e:
            self.update_stack()
        self.get_stack_status()
    
    ### This function updates and existing CF stack
    def update_stack(self):
        client = self.cloudformation_client
        client.update_stack(
            StackName=self.stack_name,
            UsePreviousTemplate=False,
            TemplateURL= self.url_nested_controller,
            Parameters=[
                {"ParameterKey": "App",
                    "ParameterValue": self.stack_name},
                {"ParameterKey": "StackUrl",
                    "ParameterValue": self.bucket_url},
            ],
            Capabilities=['CAPABILITY_NAMED_IAM'],    
        )

    ### Upload Cloudformation Files to the specified Bucket
    def upload_cf_files(self):
        client = self.s3_client
        client.create_bucket(Bucket=self.s3_bucket) ### This function creates the bucket if it doesn't exists.
        directory_path = Path().resolve()
        for root, dirs, files in os.walk(directory_path):
            for file_name in files:
                if '.yml' in file_name:
                    local_file_path = os.path.join(root, file_name)
                    client.Bucket(self.s3_bucket).upload_file(local_file_path,file_name)

    ### This function will remove the s3 bucket if it exists and all objects inside
    def remove_bucket(self):
        s3 = self.s3_client

        try:
            s3.meta.client.head_bucket(Bucket=self.s3_bucket)
            bucket = s3.Bucket(self.s3_bucket)
            bucket.objects.all().delete()
            bucket.delete()

        except ClientError:
            pass
    
    ### This function will try to destroy the stack if it exists
    def destroy_stack(self):
        client = self.cloudformation_client
        try:
            client.delete_stack(
                StackName=self.stack_name 
            )

            self.get_stack_status()
        except ClientError as e:
            pass

### This function will try to get the Aws credentials from the local env
def get_aws_credentials():

    aws_access_key_id = os.environ["aws_access_key_id"]
    if aws_access_key_id == "":
        raise ValueError('No AWS access key id found.')
    aws_secret_access_key= os.environ["aws_secret_access_key"]
    if aws_secret_access_key == "":
        raise ValueError('No AWS secret access Key found.')
    region = os.environ["region"]
    if aws_secret_access_key == "":
        raise ValueError('No AWS region found.')
    return aws_access_key_id, aws_secret_access_key, region

if __name__ == '__main__':

    action = sys.argv[1]
    stack_name = input("Stack name:\n")

    aws_access_key_id, aws_secret_access_key, region = get_aws_credentials()

    ### Create deploy object
    deploy = DeploySolvDTest(
        region=region,
        stack_name=stack_name,
        s3_bucket="solvdtestjoaouchoavaz",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )

    ### Condition for create and destroy functions
    if action == "create":
        deploy.upload_cf_files()
        deploy.create_stack()

    elif action == "destroy":
        deploy.remove_bucket()
        deploy.destroy_stack()