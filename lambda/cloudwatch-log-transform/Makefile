.PHONY: default build upload deploy clean

DEPLOY_DIR      ?= $(PWD)
ARTIFACT        ?= logs_transform.zip

S3_KEY		?= $(ARTIFACT)

STACK_NAME	?= CloudWatchLogsCleaner
TIMEOUT		?= 60

PARAMETERS	 = [
PARAMETERS	+= {"ParameterKey": "LambdaName", "ParameterValue": "$(STACK_NAME)"},
PARAMETERS	+= {"ParameterKey": "SourceBucket", "ParameterValue": "$(S3_BUCKET)"},
PARAMETERS	+= {"ParameterKey": "SourceKey", "ParameterValue": "$(S3_KEY)"},
PARAMETERS	+= {"ParameterKey": "Timeout", "ParameterValue": "$(TIMEOUT)"}
PARAMETERS	+= ]

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
		--parameters '$(PARAMETERS)'

clean:
	rm -rf $(ARTIFACT)
	rm -rf __pycache__
