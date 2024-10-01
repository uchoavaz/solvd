# SolvD Test
Write a python script that takes as input the name of a cloudformation stack and

1. outputs the current status of the stack

2. if the stack is in a rollback state, outputs the name of the resource that triggered the rollback and the error message

3. (for extra points) if the resource in #3 is a nested stack, outputs the name of the resource in the nested stack that triggered the rollback and the error message

Note:

aws credentials and region will be supplied to the script as environment variables

the script output should be json formatted.

# Prerequisites

*  Python v3.11 or higher
*  boto3 v1.26.79 or higher
*  botocore v1.29.79 or higher

Environment Variables
------------
These 3 variables are required, otherwise the script won't work.
- region
- aws_access_key_id
- aws_secret_access_key

      export region="<aws region>" (us-east-1, us-east-2 ...)
      export aws_access_key_id="<aws_access_key_id>"
      export aws_secret_access_key="<aws_secret_access_key>"

Cloudformation architecture
------------

This project deploys 1 Web page into one ec2 instance and all it dependencies to deploy an instance in a public subnet. We have in this repo 3 yml files:

 - controller.yml
     - The main cloudformation stack that will call app.yml and network.yml as nested stacks.
 - app.yml(Nested Stack)
     - Contains one Security group and one Ec2 Instance
 - network.yml(Nested Stack)
     - Contains 1 VPC, 1 public subnet, 1 Internet Gateway and 1 Route table

Creation Deployment
------------
It will push all local yml files to an s3 bucket(The script will try to create a new bucket called **solvdtestjoaouchoavaz** if it doesn't exists) and then will execute the main stack **controller.yml**, which will call the nested ones. You only need to run the command bellow and input your stack name.

      python3 deploy.py create

Destroy Deployment
------------
It will remove all the files from the s3 bucket(**solvdtestjoaouchoavaz**), remove the bucket and then will destroy the specified stack, which will destroy the nested ones. You only need to run the command bellow and input the stack name you want to destroy.

      python3 deploy.py destroy


Outputs
------------
The output Json structure is composed by:

    - {"stack_status": <Stack STATUS>, "stack_name": <Stack Name>, "nested_failed_stacks": [{"nested_stack_id": <Failed Nested Stack ID>, "nested_failed_stack_events":[{"nested_stack_status_reason": <Reason Why resource failed to deploy>, "nested_stack_physical_resource_id": <Physical resource id affected>}]}]}

- **nested_failed_stacks** is a list of dictionaries that contains the stack id's of the nested stacks affecteds. This part will only be added if the main stack faces a ROLLBACK status.
- **nested_failed_stack_events** is another list of dictionaries inside **nested_failed_stacks** that will show the Failed resources inside the nested stack.
- This output will be updated every 15 seconds.


Final Considerations
------------
If you want to see the app web page you just need to type http://<instance_public_ip>. *instance_public_ip is the public ip of the instance that the cloudformation deployed.