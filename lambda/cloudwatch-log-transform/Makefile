.PHONY: default build upload deploy clean

DEPLOY_DIR      	?= $(PWD)
ARTIFACT        	?= log_transform.zip

S3_KEY			?= $(ARTIFACT)

STACK_NAME		?= LogsTransformer

DEPLOY_PARAMETERS	 = [
DEPLOY_PARAMETERS	+= {"ParameterKey": "LambdaName", "ParameterValue": "$(STACK_NAME)"},
DEPLOY_PARAMETERS	+= {"ParameterKey": "SourceBucket", "ParameterValue": "$(S3_BUCKET)"},
DEPLOY_PARAMETERS	+= {"ParameterKey": "SourceKey", "ParameterValue": "$(S3_KEY)"},
DEPLOY_PARAMETERS	+= {"ParameterKey": "SourceStreamName", "ParameterValue": "$(SOURCE_STREAM)"},
DEPLOY_PARAMETERS	+= {"ParameterKey": "DestinationStreamName", "ParameterValue": "$(DEST_STREAM)"}
DEPLOY_PARAMETERS	+= ]


default: build

build: 
	zip $(DEPLOY_DIR)/$(ARTIFACT) *.py

upload: build
	aws s3 cp $(DEPLOY_DIR)/$(ARTIFACT) s3://$(S3_BUCKET)/$(S3_KEY)

deploy: upload
	aws cloudformation create-stack \
		--stack-name $(STACK_NAME) \
		--template-body file://cloudformation.yml \
		--capabilities CAPABILITY_NAMED_IAM \
		--parameters '$(DEPLOY_PARAMETERS)'

subscribe:
	STREAM_NAME=$$(aws cloudformation describe-stacks \
			--stack-name $(STACK_NAME) \
			--query "Stacks[].Parameters[?ParameterKey=='SourceStreamName'].ParameterValue" \
			--output text) ; \
	STREAM_ARN=$$(aws cloudformation describe-stacks \
			--stack-name $(STACK_NAME) \
			--query "Stacks[].Outputs[?OutputKey=='SourceArnOutput'].OutputValue" \
			--output text) ; \
	ROLE_ARN=$$(aws cloudformation describe-stacks \
			--stack-name $(STACK_NAME) \
			--query "Stacks[].Outputs[?OutputKey=='SubscriptionRoleOutput'].OutputValue" \
			--output text) ; \
	aws logs put-subscription-filter \
		--log-group-name $(LOG_GROUP) \
		--filter-name "Kinesis-$${STREAM_NAME}" \
		--filter-pattern "" \
		--destination-arn $${STREAM_ARN} \
		--role-arn $${ROLE_ARN}

clean:
	rm -rf $(DEPLOY_DIR)/$(ARTIFACT)
	rm -rf __pycache__
